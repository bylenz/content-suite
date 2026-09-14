# Objective

Exponer una vista/facade de observabilidad segura sobre traces ya emitidos, sin reemplazar Langfuse ni revelar secretos, prompts completos o chain-of-thought.

# Current State

El shell contiene Observability como placeholder deshabilitado. La spec 02 aporta tracer/trace IDs; los flujos posteriores los asocian con entidades. No hay endpoints ni UI de traces.

# In Scope

- Servicio/read model para listar y ver traces autorizados por brand, entidad y fecha.
- Facade `GET /api/v1/traces` y `GET /api/v1/traces/{trace_id}` basada en adapter Langfuse/read repository.
- UI de Observability con filtros mínimos, estados carga/error/vacío y detalles sanitizados; activar navegación sólo para roles definidos por contrato.
- Enlazar trace con versiones de Brand DNA/Creative/Audit cuando existan.

# Out of Scope

- Reemplazar dashboard Langfuse, reintentar modelos, editar prompts, mostrar payloads raw o implementar analytics inventadas.

# Domain / Modules Affected

`observability`, `ai`, módulos con trace IDs, frontend Observability.

# Database Changes

Sólo un índice o read model local si es estrictamente necesario; no duplicar la telemetría completa de Langfuse.

# API Changes

Añadir los endpoints facade definidos en `API.md`; paginación, filtros allowlisted y envelope de errores.

# Frontend Changes

Crear pantalla siguiendo la sidebar/superficies existentes. Nunca mostrar datos ficticios como actividad real.

# AI / RAG Changes

Muestra metadata permitida: capability, prompt version, modelo, entity reference, duración, outcome y timestamps. Excluye chain-of-thought y contenidos sensibles.

# Security / RBAC Requirements

Filtrar por membresía y brand en backend antes de consultar el trace. No aceptar `brand_id` o role de frontend como autoridad.

# Observability Requirements

La propia facade debe emitir una telemetría mínima sin recursión ni logging de secretos.

# Acceptance Criteria

- Un usuario sólo ve traces de sus marcas y entidades autorizadas.
- Las vistas no exponen secretos, tokens, prompts completos ni chain-of-thought.
- El estado sin Langfuse configurado es explícito y no rompe flujos de dominio.

# Tests Required

Fake trace repository; filtros RBAC/brand; sanitización; paginación; API + UI states.

# Manual Verification Steps

Ejecutar un flujo con fake/entorno Langfuse, abrir el trace autorizado y confirmar que una segunda marca/rol no puede acceder.

# Stop Condition

Detener si la facade se convierte en fuente de verdad, expone contenido sensible o permite invocar proveedores.
