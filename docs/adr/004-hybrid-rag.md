# ADR-004 — Hybrid RAG

**Status:** Accepted

## Problem

Similarity search puede omitir una regla crítica si no es semánticamente cercana al prompt.

## Decision

Combinar:

1. mandatory rules filtradas por metadata;
2. semantic retrieval task-specific;
3. assets relevantes cuando el task es visual.

## Consequence

La consistencia no depende exclusivamente de top-k vector search.
