# Objective

Crear la base interna de AI Platform y trazabilidad para que Knowledge, Creative y Visual Audit consuman adapters, contratos estructurados y traces sin acoplar el dominio a SDKs de proveedor.

# Current State

No existen módulos `ai` ni `observability`, dependencias de proveedores, prompt registry, contratos AI ni Langfuse. La API ya tiene configuración Pydantic, envelopes de error y arquitectura por servicios.

# In Scope

- Crear módulos `ai` y `observability` internos con interfaces `TextModel`, `EmbeddingModel` y `VisionModel`.
- Definir contratos Pydantic para output creativo, consistencia y audit; no persistir chain-of-thought.
- Crear registry versionado de prompts y capability services que reciben adapters por dependencia.
- Crear puerto de tracing Langfuse con implementación no-op explícita para desarrollo/test y adapter real configurado solo por variables de entorno.
- Registrar IDs de trace, modelo y versión de prompt donde las entidades futuras lo requieran.
- Fakes deterministas para tests y manejo explícito de proveedor no configurado.

# Out of Scope

- Ejecutar generación productiva, sincronizar Knowledge, exponer UI de traces o elegir credenciales de proveedor.
- Cambiar workflow states desde AI Platform.

# Domain / Modules Affected

`apps/api/app/ai`, `apps/api/app/observability`, configuración y tests. Consumidores posteriores: Knowledge, Creative y Visual Audit.

# Database Changes

Solo migraciones mínimas necesarias para referencias de trace/modelo que no puedan esperar a las entidades consumidoras; preferir que cada spec de dominio añada sus propias columnas.

# API Changes

Ningún endpoint de generación público en esta spec. Los errores de proveedor/contexto futuro usarán el envelope existente y 503 cuando corresponda.

# Frontend Changes

Ninguno.

# AI / RAG Changes

- Interfaces provider-agnostic y structured outputs validados con Pydantic.
- Prompt IDs iniciales: `brand.architect.v1`, `creative.*.v1`, `consistency.text.v1`, `audit.visual.v1`.
- No fallback silencioso: un adapter ausente entrega error controlado, nunca texto genérico.

# Security / RBAC Requirements

Secretos de proveedores y Langfuse se leen solo en backend. No loguear tokens, prompts con PII innecesaria ni respuestas raw sensibles.

# Observability Requirements

Cada capability expone un span/trace con entidad, prompt_version, modelo, latencia, resultado estructurado resumido y error sanitizado. El tracer no cambia estados de dominio.

# Acceptance Criteria

- Ningún router o service de dominio importa SDKs de proveedor.
- Los contratos críticos validan outputs malformados y fallan de forma explícita.
- Tests usan fakes/no-op, sin llamadas de red reales.
- Configuración ausente de proveedor/Langfuse es segura y observable.

# Tests Required

Unit tests de interfaces, prompt registry, validación Pydantic, no-op tracer y errores de adapters.

# Manual Verification Steps

Con variables de proveedor/Langfuse ausentes, iniciar API y confirmar que las capabilities responden con error controlado y sin secretos en logs.

# Stop Condition

Detener si una propuesta exige SDK de proveedor dentro de router, persistencia de chain-of-thought o cambio de workflow desde AI Platform.
