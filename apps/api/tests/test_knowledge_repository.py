"""Knowledge repository (4.1): SQLite seam (Python cosine ranking).

Validates filtering/isolation/idempotent replacement/deterministic order and
the tie-break by id — explicitly NOT pgvector numeric parity (design.md).
"""

import uuid

from app.brand_dna.schemas import BrandDnaDocument
from app.knowledge import repository
from app.knowledge.chunker import build_chunks
from app.knowledge.models import BrandKnowledgeChunk, KnowledgeScope
from tests.conftest import valid_document


def seed_version_chunks(session, brand_id: uuid.UUID, version_id: uuid.UUID) -> int:
    document = BrandDnaDocument.model_validate(valid_document())
    chunks, _ = build_chunks(version_id, document)
    embeddings = [[float(len(c.content)), 1.0, 0.5] for c in chunks]
    repository.replace_version_chunks(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        chunks=chunks,
        embeddings=embeddings,
    )
    session.commit()
    return len(chunks)


def test_isolation_between_brands_and_versions(session) -> None:
    brand_a, brand_b = uuid.uuid4(), uuid.uuid4()
    version_a1, version_a2, version_b1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    seed_version_chunks(session, brand_a, version_a1)
    seed_version_chunks(session, brand_a, version_a2)
    seed_version_chunks(session, brand_b, version_b1)

    a1 = repository.list_chunks(session, brand_id=brand_a, brand_dna_version_id=version_a1)
    a2 = repository.list_chunks(session, brand_id=brand_a, brand_dna_version_id=version_a2)
    b1 = repository.list_chunks(session, brand_id=brand_b, brand_dna_version_id=version_b1)

    assert {c.id for c in a1}.isdisjoint({c.id for c in a2})
    assert {c.id for c in a1}.isdisjoint({c.id for c in b1})
    assert {c.id for c in a2}.isdisjoint({c.id for c in b1})
    assert repository.count_chunks(session, version_a1) == len(a1)
    assert repository.count_chunks(session, version_a2) == len(a2)
    assert repository.count_chunks(session, version_b1) == len(b1)


def test_replacement_is_idempotent_preserving_ids(session) -> None:
    brand_id, version_id = uuid.uuid4(), uuid.uuid4()
    first_count = seed_version_chunks(session, brand_id, version_id)
    first = repository.list_chunks(session, brand_id=brand_id, brand_dna_version_id=version_id)

    second_count = seed_version_chunks(session, brand_id, version_id)
    second = repository.list_chunks(session, brand_id=brand_id, brand_dna_version_id=version_id)

    assert first_count == second_count
    assert [c.id for c in first] == [c.id for c in second]
    assert [c.content for c in first] == [c.content for c in second]


def test_mandatory_and_scope_filters(session) -> None:
    brand_id, version_id = uuid.uuid4(), uuid.uuid4()
    seed_version_chunks(session, brand_id, version_id)

    mandatory = repository.list_chunks(
        session, brand_id=brand_id, brand_dna_version_id=version_id, mandatory=True
    )
    semantic_scopes = repository.list_chunks(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        mandatory=False,
        scopes=[KnowledgeScope.TEXT, KnowledgeScope.BOTH],
    )

    assert mandatory and all(c.mandatory for c in mandatory)
    assert {c.rule_type for c in mandatory} == {
        "avoid_vocabulary", "dont_example", "communication_rule", "logo_usage", "restriction",
    }
    assert semantic_scopes and all(
        not c.mandatory and c.scope in (KnowledgeScope.TEXT, KnowledgeScope.BOTH)
        for c in semantic_scopes
    )


def test_ranking_is_deterministic_with_id_tiebreak(session) -> None:
    brand_id, version_id = uuid.uuid4(), uuid.uuid4()
    document = BrandDnaDocument.model_validate(valid_document())
    chunks, _ = build_chunks(version_id, document)
    # Equal embeddings for every chunk: every distance ties -> order must fall
    # back to id ASC, stably.
    embeddings = [[1.0, 0.0, 0.0]] * len(chunks)
    repository.replace_version_chunks(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        chunks=chunks,
        embeddings=embeddings,
    )
    session.commit()

    first = repository.rank_semantic(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        scopes=[KnowledgeScope.TEXT, KnowledgeScope.BOTH],
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
    )
    second = repository.rank_semantic(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        scopes=[KnowledgeScope.TEXT, KnowledgeScope.BOTH],
        query_vector=[1.0, 0.0, 0.0],
        top_k=5,
    )

    assert [r.id for r in first] == sorted(r.id for r in first)
    assert [r.id for r in first] == [r.id for r in second]
    assert len(first) == 5


def test_ranking_orders_by_distance_then_filters_version(session) -> None:
    brand_id, version_id = uuid.uuid4(), uuid.uuid4()
    # Craft three chunks with distinct distances to [1, 0, 0].
    rows = [
        BrandKnowledgeChunk(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"near-{version_id}"),
            brand_id=brand_id,
            brand_dna_version_id=version_id,
            section="voice",
            rule_type="usage_guide",
            scope=KnowledgeScope.TEXT,
            mandatory=False,
            content="closest",
            chunk_metadata={"order": 0, "field": "usage_guide", "index": None},
            embedding=[1.0, 0.0, 0.0],
        ),
        BrandKnowledgeChunk(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"mid-{version_id}"),
            brand_id=brand_id,
            brand_dna_version_id=version_id,
            section="voice",
            rule_type="audience",
            scope=KnowledgeScope.TEXT,
            mandatory=False,
            content="middle",
            chunk_metadata={"order": 1, "field": "audience", "index": None},
            embedding=[0.0, 1.0, 0.0],
        ),
        BrandKnowledgeChunk(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"far-{version_id}"),
            brand_id=brand_id,
            brand_dna_version_id=version_id,
            section="voice",
            rule_type="positioning",
            scope=KnowledgeScope.TEXT,
            mandatory=False,
            content="farthest",
            chunk_metadata={"order": 2, "field": "positioning", "index": None},
            embedding=[-1.0, 0.0, 0.0],
        ),
    ]
    session.add_all(rows)
    session.commit()

    ranked = repository.rank_semantic(
        session,
        brand_id=brand_id,
        brand_dna_version_id=version_id,
        scopes=[KnowledgeScope.TEXT],
        query_vector=[1.0, 0.0, 0.0],
        top_k=3,
    )

    assert [r.content for r in ranked] == ["closest", "middle", "farthest"]
    assert ranked[0].distance == 0.0
    # Another version's chunks never leak into the ranking.
    other = repository.rank_semantic(
        session,
        brand_id=brand_id,
        brand_dna_version_id=uuid.uuid4(),
        scopes=[KnowledgeScope.TEXT],
        query_vector=[1.0, 0.0, 0.0],
        top_k=3,
    )
    assert other == []
