"""Immutable versioned prompt registry (AI_SYSTEM.md).

Ids are `<name>.<version>`; the versioned id doubles as the `prompt_version`
recorded in traces. Resolving an unknown id raises `AIPromptNotFoundError`
without invoking any model.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.ai.errors import AIPromptNotFoundError


@dataclass(frozen=True, slots=True)
class PromptSpec:
    name: str
    version: str
    template: str

    @property
    def id(self) -> str:
        return f"{self.name}.{self.version}"


def _entry(name: str, version: str, template: str) -> tuple[str, PromptSpec]:
    spec = PromptSpec(name=name, version=version, template=template)
    return spec.id, spec


_PROMPTS: Mapping[str, PromptSpec] = MappingProxyType(
    dict(
        [
            _entry(
                "brand.architect",
                "v1",
                "You are a brand strategist. Derive the structured Brand DNA document "
                "from the provided brand brief. Respond only with JSON matching the "
                "requested BrandDNA schema.",
            ),
            _entry(
                "creative.product_description",
                "v1",
                "You are a brand-guided copywriter. Write a product description that "
                "applies the provided brand rules and retrieved brand context. Respond "
                "only with JSON matching the CreativeOutput contract with content.",
            ),
            _entry(
                "creative.video_script",
                "v1",
                "You are a brand-guided scriptwriter. Write a short video script that "
                "applies the provided brand rules and retrieved brand context. Respond "
                "only with JSON matching the CreativeOutput contract with "
                "structured_sections.",
            ),
            _entry(
                "creative.image_prompt",
                "v1",
                "You are an art director. Produce an image generation prompt that "
                "applies the provided visual brand rules. Respond only with JSON "
                "matching the CreativeOutput contract with content.",
            ),
            _entry(
                "consistency.text",
                "v1",
                "You are a brand compliance reviewer. Check the provided content "
                "against the provided brand rules. Respond only with JSON matching the "
                "ConsistencyResult contract.",
            ),
            _entry(
                "audit.visual",
                "v1",
                "You are a visual compliance auditor. Analyze the provided image "
                "against the provided mandatory visual rules. Respond only with JSON "
                "matching the VisualAuditResult contract.",
            ),
        ]
    )
)


def resolve_prompt(prompt_id: str) -> PromptSpec:
    """Return the registered spec for a versioned prompt id."""
    spec = _PROMPTS.get(prompt_id)
    if spec is None:
        raise AIPromptNotFoundError(prompt_id)
    return spec


def registered_prompt_ids() -> tuple[str, ...]:
    return tuple(_PROMPTS)
