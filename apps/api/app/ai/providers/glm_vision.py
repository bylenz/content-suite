"""GLM (Zhipu / Z.ai) vision adapter: OpenAI-compatible chat completions
behind the async `VisionModel` port.

Z.ai's Coding Plan exposes an OpenAI Chat-Completions-compatible endpoint
(https://api.z.ai/api/coding/paas/v4) serving `glm-5.3-flash`, a native
multimodal model (image/video/text/file in, text out). The `openai` SDK is
reused as a thin HTTP client pointed at that `base_url` -- no separate SDK
dependency needed, same lazy-import boundary discipline as the OpenAI
adapters. Unlike `TextModel.generate_structured`, `VisionModel.analyze_structured`
carries no response schema, so there is no provider-side schema enforcement
available here regardless of provider: `response_format: json_object` only
guarantees syntactically valid JSON, never a particular shape. Pydantic
contract validation in `app.ai.runner` remains the actual safety net, same
as every other adapter.
"""

import asyncio
import json
from typing import Any


class GLMVisionModel:
    """Async vision analysis via the blocking SDK client wrapped in `to_thread`."""

    def __init__(self, *, api_key: str, base_url: str, model: str, client: Any = None) -> None:
        if client is None:
            from openai import OpenAI  # lazy by design: this module is the SDK boundary

            client = OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self.name = model

    async def analyze_structured(
        self, *, instructions: str, prompt: str, image_ref: str
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._analyze_structured_blocking, instructions, prompt, image_ref
        )

    def _analyze_structured_blocking(
        self, instructions: str, prompt: str, image_ref: str
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_ref}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }
        response = self._client.chat.completions.create(**params)
        content = response.choices[0].message.content or ""
        return _parse_json_object(content, self.name)


def _parse_json_object(content: str, model_name: str) -> dict[str, Any]:
    from app.ai.errors import AIProviderResponseError

    text = content.strip()
    if text.startswith("```"):
        # Tolerate a markdown-fenced body: some non-OpenAI providers wrap JSON
        # mode output in a fence even when asked not to.
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[len("json") :].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIProviderResponseError(model_name) from exc
    if not isinstance(parsed, dict):
        raise AIProviderResponseError(model_name)
    return parsed
