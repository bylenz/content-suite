"""Schemas for the knowledge module (API resources, no embeddings exposed)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.brand_dna.models import KnowledgeStatus
from app.knowledge.models import KnowledgeScope

Content = Annotated[str, Field(min_length=1, max_length=10000)]
RuleType = Annotated[str, Field(min_length=1, max_length=100)]


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section: str
    rule_type: RuleType
    scope: KnowledgeScope
    mandatory: bool
    content: Content
    # The ORM attribute is `chunk_metadata` (SQLAlchemy reserves `metadata`);
    # the HTTP contract exposes the canonical DB column name `metadata`.
    metadata: dict = Field(validation_alias="chunk_metadata")
    created_at: datetime


class VersionRef(BaseModel):
    """The published version a knowledge resource belongs to."""

    id: uuid.UUID
    version: int
    knowledge_status: KnowledgeStatus


class KnowledgeChunksOut(BaseModel):
    brand_dna_version: VersionRef
    chunks: list[ChunkOut]


class KnowledgeStatusOut(BaseModel):
    brand_dna_version_id: uuid.UUID
    version: int
    knowledge_status: KnowledgeStatus
    chunk_count: int | None
    embedding_model: str | None
