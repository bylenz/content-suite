# Observability

## Principle

La UI de Observability es opcional para etapas tempranas. El tracing no.

## Langfuse traces

### Creative

```mermaid
flowchart TD
  T[creative.generate]
  R[rag.retrieve]
  P[prompt.build]
  G[llm.generate]
  C[consistency.evaluate]

  T --> R
  T --> P
  T --> G
  T --> C
```

### Visual Audit

```mermaid
flowchart TD
  T[visual.audit]
  R[rag.retrieve_visual]
  L[asset.load]
  V[vision.analyze]
  B[compliance.build]

  T --> R
  T --> L
  T --> V
  T --> B
```

## Trace metadata

```text
brand_id
brand_dna_version_id
creative_item_id?
creative_version_id?
visual_asset_id?
user_id
role
model
prompt_version
retrieved_rule_ids
latency_ms
status
```

## Domain links

Persistir `langfuse_trace_id` en:
- AI-generated creative versions;
- visual audits;
- otras entidades donde ayude a reproducibilidad.

## Metrics útiles

MVP:
- provider latency;
- failures;
- retrieval count;
- audit duration.

No construir dashboards de infraestructura innecesarios.
