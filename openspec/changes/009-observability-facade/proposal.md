# Proposal: 009-observability-facade

## Why

Los traces sanitizados existen solo dentro de Langfuse (change 005) y no hay forma autorizada de verlos desde el producto: el shell muestra "Observability" como placeholder deshabilitado. La spec `specs/07-observability-facade.md` pide una facade de lectura segura sobre traces ya emitidos, sin reemplazar Langfuse ni exponer secretos, prompts completos o chain-of-thought.

## What Changes

- Nuevo read model local mínimo (`observability_trace_index`) con metadatos sanitizados allowlist, poblado en el punto de emisión del span; no duplica la telemetría completa de Langfuse.
- Extensión aditiva de `CapabilitySpan` y del runner con contexto opcional de entidad/brand (escalares allowlist), sin romper llamadores existentes.
- Facade `GET /api/v1/traces` y `GET /api/v1/traces/{trace_id}` (según `API.md`): paginación, filtros allowlist (brand, entidad, fecha) y envelope de errores existente.
- Autorización en backend: sólo traces de marcas con membresía del usuario; `brand_id`/role del frontend nunca son autoridad.
- Estado explícito cuando Langfuse no está configurado (y lista vacía cuando no hay traces), sin romper flujos de dominio.
- Pantalla frontend Observability con filtros mínimos, estados carga/error/vacío y detalle sanitizado; navegación activada para los roles definidos por contrato.
- Binding de trace con versiones de Brand DNA/Creative/Audit cuando existan (columnas de referencia en el índice; Creative/Audit aún no existen y enlazarán por estas columnas en sus changes).

## Capabilities

### New Capabilities

- `observability-facade`: lectura autorizada y sanitizada de traces (endpoints facade, read model local, RBAC por brand, estados explícitos, UI de observabilidad).

### Modified Capabilities

<!-- Ninguna: observability-tracing (change 005, aún no archivada) no cambia sus requirements; esta change solo consume su puerto de emisión de forma aditiva. -->

## Impact

- `apps/api/app/observability` (nuevo read model, repository, service, adaptador de grabación), `apps/api/app/ai` (parámetros opcionales de contexto en runner/span), `apps/api/alembic` (una migración), `apps/api/app/main.py` (router nuevo).
- `apps/web/src/features/observability` (nueva), `apps/web/src/features/shell/nav.ts` (activar item), `apps/web/src/shared/api` (cliente de endpoints).
- API pública: dos endpoints GET nuevos bajo `/api/v1/traces` (aditivo).
- Sin dependencias nuevas obligatorias; Langfuse sigue siendo opcional y la fuente profunda de telemetría.
