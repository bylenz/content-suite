# API

Base: `/api/v1`

## Convenciones

- JSON.
- UUIDs.
- UTC en persistencia.
- JWT Bearer.
- Pydantic request/response models.
- 409 para transición inválida.
- 403 para falta de permiso.
- 503 cuando Brand Knowledge o AI provider requerido no está disponible.

## Current User

```http
GET /api/v1/me
```

## Brand DNA

```http
GET   /api/v1/brands/{brand_id}/brand-dna
POST  /api/v1/brands/{brand_id}/brand-dna/generate
PATCH /api/v1/brands/{brand_id}/brand-dna/draft
POST  /api/v1/brands/{brand_id}/brand-dna/publish
GET   /api/v1/brands/{brand_id}/brand-dna/versions
```

## Knowledge

```http
GET  /api/v1/brands/{brand_id}/brand-knowledge
GET  /api/v1/brands/{brand_id}/brand-knowledge/status
POST /api/v1/brands/{brand_id}/brand-knowledge/sync
```

## Brand Assets

```http
POST   /api/v1/brands/{brand_id}/assets
GET    /api/v1/brands/{brand_id}/assets
DELETE /api/v1/brands/{brand_id}/assets/{asset_id}
```

## Creative

```http
POST /api/v1/creative-items
GET  /api/v1/creative-items
GET  /api/v1/creative-items/pipeline
GET  /api/v1/creative-items/{item_id}

POST /api/v1/creative-items/{item_id}/generate
POST /api/v1/creative-items/{item_id}/regenerate
POST /api/v1/creative-items/{item_id}/versions
GET  /api/v1/creative-items/{item_id}/versions
GET  /api/v1/creative-items/{item_id}/versions/{version_id}

POST /api/v1/creative-items/{item_id}/consistency-check
GET  /api/v1/creative-items/{item_id}/applied-context
POST /api/v1/creative-items/{item_id}/submit
```

## Content Review

```http
GET  /api/v1/content-reviews/queue
GET  /api/v1/content-reviews/{item_id}
POST /api/v1/content-reviews/{item_id}/approve
POST /api/v1/content-reviews/{item_id}/request-changes
GET  /api/v1/content-reviews/{item_id}/history
```

## Visual Review

```http
GET  /api/v1/visual-reviews/queue

POST /api/v1/creative-items/{item_id}/visual-assets
GET  /api/v1/creative-items/{item_id}/visual-assets

POST /api/v1/visual-assets/{asset_id}/audit
GET  /api/v1/visual-assets/{asset_id}/audit

POST /api/v1/visual-audits/{audit_id}/approve
POST /api/v1/visual-audits/{audit_id}/request-changes

GET /api/v1/creative-items/{item_id}/visual-audit-history
```

## Observability Facade

```http
GET /api/v1/traces
GET /api/v1/traces/{trace_id}
```

Esta facade nunca reemplaza Langfuse.

## Dashboard Activity

```http
GET /api/v1/creative-items/pipeline?brand_id
GET /api/v1/activity?brand_id&limit&offset
```

Ambos endpoints son de solo lectura, sin migración: leen `creative_items`,
`workflow_events` y `brand_dna_versions` ya existentes. `brand_id` es siempre
explícito (a diferencia de la facade de observabilidad, no hay modo
"agregado sin marca"). 403 si el actor no tiene membresía en `brand_id`.

`pipeline` devuelve el conteo de creative items por cada uno de los 7 valores
reales de `workflow_status`, con cero explícito en los estados sin items.

`activity` devuelve un feed paginado (`limit` 1-50 default 20, `offset`,
`total`) que fusiona `workflow_events` de la marca con un evento derivado por
cada versión de Brand DNA publicada (`published_at`/`created_by`), en orden
cronológico descendente. No incluye auditoría de IA ni sincronización de
Knowledge (change 014: sin fuente de evento persistida hoy).

## Response Error Shape

```json
{
  "error": {
    "code": "INVALID_WORKFLOW_TRANSITION",
    "message": "Creative item cannot be approved from its current state.",
    "details": {}
  }
}
```

## Idempotencia

Commands sensibles a doble-click/retry deben tolerarlo o usar idempotency key:
- publish Brand DNA;
- submit content;
- approve/request changes;
- run audit cuando corresponda;
- approve final visual.
