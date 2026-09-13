# ADR-002 — Supabase PostgreSQL + pgvector

**Status:** Accepted

## Decision

Usar PostgreSQL como persistencia canónica y pgvector para embeddings.

Supabase aporta:
- hosted Postgres;
- Auth;
- Storage;
- pgvector.

## Important

Los embeddings no son la fuente de verdad. Brand DNA versionado permanece en PostgreSQL como JSON estructurado.
