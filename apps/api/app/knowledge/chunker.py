"""Deterministic chunking of a published Brand DNA document (design.md mapping).

One chunk per atomic unit, traversed in a fixed section order. `id` is a UUIDv5
derived from the version and the canonical field/index, so re-syncing the same
immutable document reproduces the exact same IDs and any two versions/units
never collide. The fingerprint is a SHA-256 over the canonical serialization of
the ordered chunk set; the sync claim compares it to decide idempotency vs
regeneration of the derived (replaceable) chunks.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from app.brand_dna.schemas import BrandDnaDocument
from app.knowledge.models import KnowledgeScope

# Fixed namespace for knowledge chunk ids (documented constant; never change:
# existing persisted ids would stop being reproducible).
CHUNK_NAMESPACE = uuid.UUID("7d3e6f21-9c48-4a6b-8d15-2f0e4c8a1b97")


@dataclass(frozen=True, slots=True)
class Chunk:
    """One atomic knowledge unit with its deterministic identity."""

    id: uuid.UUID
    section: str
    rule_type: str
    scope: KnowledgeScope
    mandatory: bool
    content: str
    metadata: dict


def _chunk_id(version_id: uuid.UUID, order: int, field: str, index: int | None) -> uuid.UUID:
    return uuid.uuid5(CHUNK_NAMESPACE, f"{version_id}|{order}|{field}|{index}")


class _Builder:
    def __init__(self, version_id: uuid.UUID) -> None:
        self.version_id = version_id
        self.chunks: list[Chunk] = []
        self._order = 0

    def add(
        self,
        *,
        section: str,
        field: str,
        rule_type: str,
        scope: KnowledgeScope,
        mandatory: bool,
        content: str,
        index: int | None = None,
    ) -> None:
        order = self._order
        self._order += 1
        self.chunks.append(
            Chunk(
                id=_chunk_id(self.version_id, order, field, index),
                section=section,
                rule_type=rule_type,
                scope=scope,
                mandatory=mandatory,
                content=content,
                metadata={"order": order, "field": field, "index": index},
            )
        )


def build_chunks(version_id: uuid.UUID, document: BrandDnaDocument) -> tuple[list[Chunk], str]:
    """Derive the canonical chunk set + fingerprint for a published document.

    Pure CPU over the immutable document: no DB, no awaits, deterministic.
    """
    b = _Builder(version_id)
    # identity
    b.add(section="identity", field="purpose", rule_type="purpose", scope=KnowledgeScope.TEXT,
          mandatory=False, content=document.identity.purpose)
    b.add(section="identity", field="positioning", rule_type="positioning",
          scope=KnowledgeScope.TEXT, mandatory=False, content=document.identity.positioning)
    b.add(section="identity", field="personality_traits", rule_type="personality_traits",
          scope=KnowledgeScope.TEXT, mandatory=False,
          content=", ".join(document.identity.personality_traits))
    b.add(section="identity", field="audience", rule_type="audience", scope=KnowledgeScope.TEXT,
          mandatory=False, content=document.identity.audience)
    # voice
    b.add(section="voice", field="usage_guide", rule_type="usage_guide", scope=KnowledgeScope.TEXT,
          mandatory=False, content=document.voice.usage_guide)
    b.add(section="voice", field="tone_characteristics", rule_type="tone_characteristics",
          scope=KnowledgeScope.TEXT, mandatory=False,
          content=", ".join(document.voice.tone_characteristics))
    b.add(section="voice", field="preferred_vocabulary", rule_type="preferred_vocabulary",
          scope=KnowledgeScope.TEXT, mandatory=False,
          content=", ".join(document.voice.preferred_vocabulary))
    b.add(section="voice", field="avoid_vocabulary", rule_type="avoid_vocabulary",
          scope=KnowledgeScope.TEXT, mandatory=True,
          content=", ".join(document.voice.avoid_vocabulary))
    for i, example in enumerate(document.voice.do_examples):
        b.add(section="voice", field="do_examples", rule_type="do_example",
              scope=KnowledgeScope.TEXT, mandatory=False, content=example, index=i)
    for i, example in enumerate(document.voice.dont_examples):
        b.add(section="voice", field="dont_examples", rule_type="dont_example",
              scope=KnowledgeScope.TEXT, mandatory=True, content=example, index=i)
    # communication
    for i, pillar in enumerate(document.communication.message_pillars):
        b.add(section="communication", field="message_pillars", rule_type="message_pillar",
              scope=KnowledgeScope.TEXT, mandatory=False,
              content=f"{pillar.name}: {pillar.description}", index=i)
    for i, rule in enumerate(document.communication.rules):
        b.add(section="communication", field="rules", rule_type="communication_rule",
              scope=KnowledgeScope.TEXT, mandatory=True, content=rule, index=i)
    # visual_rules (strictly textual visual context; no physical assets in this change)
    b.add(section="visual_rules", field="visual_personality", rule_type="visual_personality",
          scope=KnowledgeScope.VISUAL, mandatory=False,
          content=document.visual_rules.visual_personality)
    b.add(section="visual_rules", field="imagery_direction", rule_type="imagery_direction",
          scope=KnowledgeScope.VISUAL, mandatory=False,
          content=document.visual_rules.imagery_direction)
    b.add(section="visual_rules", field="composition", rule_type="composition",
          scope=KnowledgeScope.VISUAL, mandatory=False, content=document.visual_rules.composition)
    b.add(section="visual_rules", field="logo_usage", rule_type="logo_usage",
          scope=KnowledgeScope.VISUAL, mandatory=True, content=document.visual_rules.logo_usage)
    # restrictions
    for i, rule in enumerate(document.restrictions.rules):
        b.add(section="restrictions", field="rules", rule_type="restriction",
              scope=KnowledgeScope.BOTH, mandatory=True, content=rule, index=i)
    return b.chunks, fingerprint_for(b.chunks)


def fingerprint_for(chunks: list[Chunk]) -> str:
    """SHA-256 over the canonical serialization of the ordered chunk set."""
    canonical = [
        [str(c.id), c.section, c.rule_type, c.scope.value, c.mandatory, c.content, c.metadata]
        for c in chunks
    ]
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
