# ADR-005 — AI Provider Abstraction

**Status:** Accepted

## Decision

El dominio depende de interfaces:

- `TextModel`
- `VisionModel`
- `EmbeddingModel`

Los SDKs concretos viven en `ai/providers/`.

## Why

El reto puede iniciar con Groq/Gemini sin acoplar contratos de dominio a un proveedor.
