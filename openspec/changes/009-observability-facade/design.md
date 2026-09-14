# Design: 009-observability-facade

## Context

Ver `proposal.md` y la delta `observability-facade`. La change 005 dejó el puerto `Tracer` (no-op + adapter Langfuse), spans sanitizados (`CapabilitySpan` + `TraceSummary`) y el runner `run_capability` — hoy sin llamadores en rutas productivas. No existe persistencia local de traces, ni endpoints, ni UI: el item "Observability" del shell es un placeholder. `specs/07-observability-facade.md` pide una facade de lectura segura; `API.md` ya reserva `GET /api/v1/traces` y `GET /api/v1/traces/{trace_id}`.

## Goals / Non-Goals

**Goals:**

- Lectura autorizada (membresía resuelta en backend) de traces sanitizadas por brand, entidad y fecha, con paginación.
- Read model local mínimo que funciona con y sin Langfuse, con estado explícito.
- UI Observability con filtros mínimos y estados carga/error/vacío.

**Non-Goals:**

- No reemplazar el dashboard de Langfuse ni reintentar/editar prompts; sin payloads raw ni analytics inventadas.
- No añadir capabilities ni consumidores de `run_capability` (eso llega con creative/visual audit).
- No introducir workers, colas ni sincronización batch desde Langfuse.

## Decisions

### Read model local (`observability_trace_index`) en lugar de adapter de lectura Langfuse

Una tabla única con la fila sanitizada por span: `trace_id` (text nullable), `brand_id` (uuid nullable, FK), `entity_type` (text), `entity_id` (uuid nullable), `operation`, `prompt_version`, `model` (nullables), `latency_ms`, `outcome` (`ok`/`error`), `error_type` (nullable), `created_at` (por defecto `now()`), `langfuse_configured_at_emit` innecesario — no se persiste. Índice `(brand_id, created_at DESC)` + índice `(entity_type, entity_id)`.

Alternativa descartada: consultar la API de lectura de Langfuse en tiempo de request. Los spans actuales no llevan `brand_id` en metadatos, obligaría a filtrar post-fetch (ineficiente y frágil), acopla la latencia del endpoint a Langfuse y no degrada de forma controlada sin credenciales. El índice local permite filtrado por membresía en SQL, paginación determinista y estado explícito sin Langfuse; no duplica telemetría completa (solo escalares allowlist).

### Grabación en el punto de emisión mediante un tracer compuesto

`observability` añade `RecordingTracer` (decorador): recibe el tracer resuelto y un `TraceRecordRepository`; persiste la fila sanitizada y delega la emisión. El composition root resuelve `resolve_tracer(settings)` y lo envuelve. `run_capability` y los adapters no cambian su contrato de emisión; el fallo de escritura se captura y registra sanitizado (misma política que el guard del runner). La escritura es async y vía repository, sin SQL en routers ni servicios.

Alternativa descartada: escribir desde el runner. Convertiría al runner en consumidor de un segundo puerto y duplicaría la política de guard que ya existe en un solo lugar.

### Contexto de entidad opcional en el span

`CapabilitySpan` gana campos opcionales escalares: `brand_id: str | None`, `entity_type: str | None`, `entity_id: str | None`; `run_capability` los recibe como kwargs opcionales con pass-through (llamadores existentes intactos). El adapter Langfuse NO añade estos campos a sus metadatos en esta change (mantener el contrato 005; el binding local vive en el índice). Validación: si llega `entity_id` sin `entity_type` (o viceversa), error de construcción explícito.

Alternativa descartada: columnas dedicadas `brand_dna_version_id`/`creative_version_id`/`visual_audit_id`. El par genérico cubre los tres bindings sin tres columnas redundantes y sin migrar de nuevo por cada entidad futura.

### Endpoints, filtros y paginación

`GET /api/v1/traces`: `brand_id` (uuid opcional — sin él, todas las marcas autorizadas), `entity_type` (enum allowlist: `brand_dna_version`, `creative_version`, `visual_audit`), `entity_id` (uuid, requiere `entity_type`), `from`/`to` (ISO 8601), `limit` (1–50, default 20), `offset` (default 0). Respuesta: `{ "items": [...], "total": int, "langfuse_configured": bool }` — el booleano expone el estado sin Langfuse sin secretos. `GET /api/v1/traces/{trace_id}`: 404 si no existe o si su `brand_id` no está autorizado (no revelar existencia cruzada). Router -> service -> repository siguiendo el patrón `identity`/`brand_dna`; errores con envelope existente.

Alternativa descartada: `brand_id` obligatorio. La cola agregada de marcas autorizadas es útil para el dashboard y el filtro por marca es una decisión de UI, no de autorización.

### Facade sin recursión

Las lecturas de la facade emiten solo logs estructurados sanitizados (operación, duración, outcome, conteos). No emiten spans ni filas de índice: sus lecturas no se indexan a sí mismas y no hay dependencia del tracer en el servicio de lectura.

### UI feature-first con contratos propios

`apps/web/src/features/observability` con página, filtros (marca propia, tipo de entidad, fecha), tabla/lista y panel de detalle; TanStack Query para server state; cliente API en `shared/api` siguiendo el patrón existente. Item de nav activado para los tres roles (Creator, Content Reviewer, Visual Reviewer) con alcance a sus marcas: ver metadatos sanitizados de sus marcas no expone nada que el rol no pueda operar. Estados de carga, error (con reintento) y vacío diferenciados; banner explícito cuando `langfuse_configured=false`; jamás datos ficticios. Superficies según `docs/UI_UX.md` (clay reservado a navegación/tarjetas; listas de datos tenues, contraste AA) y jerarquía del starter-design.

### Tests sin Langfuse real

Fake de `TraceRecordRepository`, fakes de tracer/repository en la capa API y fakes de datos en la UI. Cobertura: filtros RBAC/brand (403/404), sanitización del payload (sin campos libres), paginación y límites, estado sin Langfuse, escritura del índice con no-op y fallo de escritura tolerado, estados de UI. Auditoría estática: `langfuse` solo se importa en `observability/langfuse_adapter.py`.

## Risks / Trade-offs

- [El índice crece con cada span] → filas de escalares acotados, índices definidos; sin retención en MVP (volumen de demo).
- [Doble fuente (índice vs Langfuse) puede divergir] → el índice es derivado y declarado no fuente de verdad; Langfuse manda para telemetría profunda; stop condition de la spec vigila la deriva.
- [Sin consumidores productivos aún, la demo no muestra datos reales] → la verificación manual usa un flujo scripted con fake adapter que emite spans reales por el runner; la UI nunca inventa filas.

## Migration Plan

1. Additive: migración nueva (tabla + índices), módulo y router nuevos, campos opcionales en span/runner, feature frontend nueva.
2. Verificación: `uv run ruff check`, `uv run ty check`, `uv run pytest` en `apps/api`; `npm run lint && npm run typecheck && npm run test` en `apps/web`; `openspec validate 009-observability-facade --strict`.
3. Rollback: eliminar migración, módulo, router y feature; los campos opcionales añadidos no rompen a llamadores existentes.

## Open Questions

- Ninguna bloqueante. La retención del índice y un hipotético deep-link a Langfuse quedan para una change futura si hacen falta.
