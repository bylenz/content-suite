# Tasks: 009-observability-facade

## 1. Read model y persistencia

- [x] 1.1 Migración Alembic additive: tabla `observability_trace_index` (`trace_id` text nullable, `brand_id` uuid nullable FK, `entity_type` text NOT NULL, `entity_id` uuid nullable, `operation` text nullable, `prompt_version` text nullable, `model` text nullable, `latency_ms` float, `outcome` enum(`ok`,`error`), `error_type` text nullable, `created_at` timestamptz default now()) con índices `(brand_id, created_at DESC)` y `(entity_type, entity_id)`; verificar coherencia con `DATA_MODEL.md`.
- [x] 1.2 Modelo SQLAlchemy y esquemas Pydantic de lectura (`TraceRecord`, `TraceListResponse` con `items`/`total`/`langfuse_configured`) con `extra="forbid"` donde aplique.
- [x] 1.3 Puerto `TraceRecordRepository` (async: `save`, `list`, `get_by_trace_id`) + implementación SQL y fake determinista para tests.

## 2. Grabación en la emisión

- [x] 2.1 `CapabilitySpan` + kwargs opcionales en `run_capability` (`brand_id`, `entity_type`, `entity_id`, pass-through; validación excluyente `entity_id` ⇔ `entity_type`); llamadores y tests existentes siguen pasando.
- [x] 2.2 `RecordingTracer` (decorador): persiste fila sanitizada vía repository capturando fallos de escritura con log sanitizado, y delega `emit_span` al tracer interno; sin escritura cuando el span carece de `entity_type` (spans legacy) — decidir y documentar en código.
- [x] 2.3 Composition root: envolver `resolve_tracer(settings)` con `RecordingTracer(repository)` e inyectar en los servicios que ya consumen el tracer; exponer `langfuse_configured` derivado de settings para la facade.

## 3. API facade

- [x] 3.1 Router `observability` registrado en `main.py`: `GET /api/v1/traces` con filtros allowlist (`brand_id`, `entity_type`, `entity_id` + `entity_type`, `from`, `to`, `limit` 1–50 default 20, `offset`), parámetros fuera del allowlist ignorados.
- [x] 3.2 Servicio de facade: resolver marcas autorizadas por membresía (módulo identity) ANTES de consultar; sin `brand_id` agrega todas las marcas autorizadas; traces sin `brand_id` jamás listables.
- [x] 3.3 `GET /api/v1/traces/{trace_id}`: 404 si no existe o la marca no está autorizada (sin revelar existencia cruzada); respuesta solo con metadatos allowlist.
- [x] 3.4 Envelope de errores existente: 403 sin membresía, 422 parámetros inválidos, 404 detalle; logs estructurados sanitizados de lectura (sin spans: sin recursión).

## 4. Frontend Observability

- [x] 4.1 Cliente API en `shared/api` + hooks TanStack Query (lista con filtros y paginación, detalle).
- [x] 4.2 `features/observability`: página con filtros mínimos (marca propia, tipo de entidad, rango de fecha), lista paginada y panel de detalle sanitizado; estados carga/error (con reintento)/vacío diferenciados; banner explícito cuando `langfuse_configured=false`; sin datos ficticios.
- [x] 4.3 Activar item Observability en `features/shell/nav.ts` para los tres roles; superficies según `docs/UI_UX.md` y starter-design (clay solo en superficies elevadas, listas tenues, contraste AA).

## 5. Tests

- [x] 5.1 Backend: repository fake + recording tracer (no-op con `trace_id` nulo, fallo de escritura tolerado), filtros RBAC/brand (403/404, trace sin brand no listable), sanitización del payload, paginación/límites, filtro fuera de allowlist ignorado, estado `langfuse_configured`.
- [x] 5.2 Frontend: render de estados (carga/error/vacío/con datos), filtro por marca propia, banner sin Langfuse, detalle sin campos no allowlist.
- [x] 5.3 Auditoría estática de imports: `langfuse` solo en `observability/langfuse_adapter.py`; sin SQL en routers; sin SDK de proveedor fuera de `ai/providers`.

## 6. Verificación

- [x] 6.1 `uv run ruff check`, `uv run ty check`, `uv run pytest` en `apps/api`; `npm run lint`, `npm run typecheck`, `npm run test` en `apps/web`.
- [x] 6.2 Verificación manual scripted: flujo con fake adapter que emite span real por el runner → trace visible para la marca autorizada; segunda marca/rol sin acceso (403/404); estado sin Langfuse explícito.
- [x] 6.3 Actualizar `API.md` solo si el contrato difiere de lo ya documentado; `openspec validate 009-observability-facade --strict`.
