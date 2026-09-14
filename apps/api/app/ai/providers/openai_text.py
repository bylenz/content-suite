"""OpenAI text adapter: chat completions behind the async `TextModel` port.

Same boundary rules as the embeddings adapter: the SDK import is lazy
(constructor), blocking SDK calls run in `asyncio.to_thread`, and the client is
injectable so tests stub it without any network. `generate_structured` asks the
provider to enforce `response_schema` server-side via strict `json_schema`
response formatting (not loose `json_object` mode, which lets the model nest
or reshape the payload) and parses the result; an unparseable body raises
`AIProviderResponseError` (sanitized 503 at the API boundary) instead of
leaking provider payloads. Contract validation in `app.ai.runner` remains the
actual safety net -- this is defense in depth, not a replacement for it.
"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any

# Keywords OpenAI's strict json_schema mode understands. Anything else
# (minLength, pattern, default, format, ...) is dropped rather than risk a
# provider-side "unsupported schema" error; Pydantic still enforces those
# constraints when the runner validates the parsed output against the
# contract, so dropping them here does not weaken validation.
_ALLOWED_SCHEMA_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "anyOf",
    "$ref",
    "description",
    "title",
}


def _strict_node(node: Mapping[str, Any]) -> dict[str, Any]:
    """Rewrite one schema node to satisfy OpenAI strict mode: every property is
    required (optionality is expressed via `anyOf` null branches, not
    omission) and objects reject unknown keys."""
    result = {key: value for key, value in node.items() if key in _ALLOWED_SCHEMA_KEYS}
    if "properties" in result:
        result["properties"] = {
            key: _strict_node(value) for key, value in result["properties"].items()
        }
        result["required"] = list(result["properties"])
        result["additionalProperties"] = False
    if "items" in result:
        result["items"] = _strict_node(result["items"])
    if "anyOf" in result:
        result["anyOf"] = [_strict_node(item) for item in result["anyOf"]]
    return result


def _strict_schema(response_schema: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a Pydantic `model_json_schema()` into an OpenAI strict schema.

    Pydantic's `$defs` (nested models referenced via `$ref`) sit alongside the
    root, not under `properties`, so they need their own pass.
    """
    root = _strict_node(response_schema)
    defs = response_schema.get("$defs")
    if defs:
        root["$defs"] = {name: _strict_node(definition) for name, definition in defs.items()}
    return root


class OpenAITextModel:
    """Async text generation via the blocking SDK client wrapped in `to_thread`."""

    def __init__(self, *, api_key: str, model: str, client: Any = None) -> None:
        if client is None:
            from openai import OpenAI  # lazy by design: this module is the SDK boundary

            client = OpenAI(api_key=api_key)
        self._client = client
        self.name = model

    async def generate(self, *, instructions: str, prompt: str) -> str:
        return await asyncio.to_thread(self._generate_blocking, instructions, prompt)

    async def generate_structured(
        self, *, instructions: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._generate_structured_blocking, instructions, prompt, response_schema
        )

    def _messages(self, instructions: str, prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ]

    def _generate_blocking(self, instructions: str, prompt: str) -> str:
        params: dict[str, Any] = {
            "model": self.name,
            "messages": self._messages(instructions, prompt),
        }
        response = self._client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    def _generate_structured_blocking(
        self, instructions: str, prompt: str, response_schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        name = response_schema.get("title") or "Response"
        params: dict[str, Any] = {
            "model": self.name,
            "messages": self._messages(instructions, prompt),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "schema": _strict_schema(response_schema),
                    "strict": True,
                },
            },
        }
        response = self._client.chat.completions.create(**params)
        content = response.choices[0].message.content or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            from app.ai.errors import AIProviderResponseError

            raise AIProviderResponseError(self.name) from exc
        if not isinstance(parsed, dict):
            from app.ai.errors import AIProviderResponseError

            raise AIProviderResponseError(self.name)
        return parsed
