"""Chunker (2.1): deterministic chunks, stable UUIDv5 ids, canonical mapping,
fingerprint sensitivity. Pure CPU; no DB, no network."""

import uuid

from app.brand_dna.schemas import BrandDnaDocument
from app.knowledge import chunker
from app.knowledge.models import KnowledgeScope
from tests.conftest import valid_document


def build(version_id: uuid.UUID, document: BrandDnaDocument):
    return chunker.build_chunks(version_id, document)


def test_same_document_yields_identical_chunks_and_ids() -> None:
    version_id = uuid.uuid4()
    doc = BrandDnaDocument.model_validate(valid_document())

    first_chunks, first_fp = build(version_id, doc)
    second_chunks, second_fp = build(version_id, doc)

    assert first_chunks == second_chunks
    assert first_fp == second_fp


def test_rechunking_reproduces_the_same_ids() -> None:
    version_id = uuid.uuid4()
    doc = BrandDnaDocument.model_validate(valid_document())

    first_ids = [c.id for c in build(version_id, doc)[0]]
    second_ids = [c.id for c in build(version_id, doc)[0]]

    assert first_ids == second_ids


def test_ids_are_disjoint_across_versions_and_fields() -> None:
    doc = BrandDnaDocument.model_validate(valid_document())
    version_a, version_b = uuid.uuid4(), uuid.uuid4()

    ids_a = {c.id for c in build(version_a, doc)[0]}
    ids_b = {c.id for c in build(version_b, doc)[0]}

    assert not ids_a & ids_b
    # Within one version every id is unique (order is part of the UUIDv5 input).
    assert len(ids_a) == len(build(version_a, doc)[0])


def test_coverage_matches_the_canonical_mapping() -> None:
    doc = BrandDnaDocument.model_validate(valid_document())
    chunks, _ = build(uuid.uuid4(), doc)

    expected = (
        4  # identity: purpose, positioning, traits (join), audience
        + 4  # voice guides/joins: usage_guide, tone, preferred, avoid
        + len(doc.voice.do_examples)
        + len(doc.voice.dont_examples)
        + len(doc.communication.message_pillars)
        + len(doc.communication.rules)
        + 4  # visual_rules narratives
        + len(doc.restrictions.rules)
    )
    assert len(chunks) == expected
    # Metadata carries the canonical order/field/index triple.
    orders = [c.metadata["order"] for c in chunks]
    assert orders == list(range(len(chunks)))
    assert all(c.metadata["index"] is None or isinstance(c.metadata["index"], int) for c in chunks)


def test_mandatory_flags_are_exact() -> None:
    chunks, _ = build(uuid.uuid4(), BrandDnaDocument.model_validate(valid_document()))
    mandatory_rules = {c.rule_type for c in chunks if c.mandatory}

    assert mandatory_rules == {
        "avoid_vocabulary",
        "dont_example",
        "communication_rule",
        "logo_usage",
        "restriction",
    }


def test_scopes_are_text_visual_both() -> None:
    chunks, _ = build(uuid.uuid4(), BrandDnaDocument.model_validate(valid_document()))
    by_rule = {c.rule_type: c.scope for c in chunks}

    assert by_rule["purpose"] == KnowledgeScope.TEXT
    assert by_rule["visual_personality"] == KnowledgeScope.VISUAL
    assert by_rule["logo_usage"] == KnowledgeScope.VISUAL
    assert by_rule["restriction"] == KnowledgeScope.BOTH
    assert by_rule["usage_guide"] == KnowledgeScope.TEXT


def test_fingerprint_is_sensitive_to_content() -> None:
    base = valid_document()
    changed = valid_document()
    changed["identity"]["purpose"] = "Different purpose entirely"

    _, base_fp = build(uuid.uuid4(), BrandDnaDocument.model_validate(base))
    _, changed_fp = build(uuid.uuid4(), BrandDnaDocument.model_validate(changed))

    assert base_fp != changed_fp


def test_list_joins_produce_one_chunk_per_list_and_items_are_sliced() -> None:
    doc = BrandDnaDocument.model_validate(valid_document())
    chunks, _ = build(uuid.uuid4(), doc)

    traits = [c for c in chunks if c.rule_type == "personality_traits"]
    dos = [c for c in chunks if c.rule_type == "do_example"]
    pillars = [c for c in chunks if c.rule_type == "message_pillar"]

    assert len(traits) == 1
    assert traits[0].content == ", ".join(doc.identity.personality_traits)
    assert [c.content for c in dos] == doc.voice.do_examples
    assert [c.content for c in pillars] == [
        f"{p.name}: {p.description}" for p in doc.communication.message_pillars
    ]
    assert [c.metadata["index"] for c in dos] == list(range(len(dos)))
