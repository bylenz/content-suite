## Why

La foundation entregó identidad, membresías, persistencia y shell, pero el producto aún no tiene su fuente de verdad operativa. Sin un Brand DNA estructurado, versionado y publicado no existe base para Knowledge, generación AI ni auditorías posteriores; esta capability es el siguiente paso del pipeline `Brand Brief -> Brand DNA -> Brand Knowledge` y convierte el shell en un flujo de producto real.

## What Changes

- Nuevo módulo backend `brand_dna` (router -> application service -> repository + policies) dentro del modular monolith, reutilizando la frontera de identidad y las políticas de membresía existentes.
- Nueva tabla `brand_dna_versions` con migración Alembic: versionado por marca, estados `DRAFT`/`ACTIVE`/`ARCHIVED`, `knowledge_status` y documentos publicados inmutables.
- Endpoints iniciales alineados con `API.md` (sin el endpoint de generación AI): lectura del DNA vigente, edición de borrador, publicación, listado y detalle de versiones, con contratos de lectura por rol: revisores solo ven `ACTIVE`/`ARCHIVED` y jamás reciben recurso, id, número de versión, conteos, metadatos ni documento de un borrador; el Creator lee además su borrador completo. El `OUTDATED` de la versión activa solo comunica cambios pendientes genéricos y no prueba ni identifica un borrador.
- Autorización backend: escritura (crear/editar/publicar) exclusiva de `CREATOR`; revisores (`CONTENT_REVIEWER`, `VISUAL_REVIEWER`) solo lectura de versiones publicadas; sin membresía o sin identidad válida se rechaza.
- Documento DNA canónico y estricto en cinco secciones operativas (identidad, voz, comunicación, reglas visuales y restricciones): tipos, cardinalidades, límites, normalización de espacios, rechazo de campos desconocidos y 422 con rutas de campo.
- Semántica transaccional y concurrente de mutaciones y publicación: las mutaciones del borrador y la publicación (`DRAFT -> ACTIVE`, con la versión `ACTIVE` anterior transicionada a `ARCHIVED` y confirmada antes de activar la nueva) se serializan con el mismo bloqueo de fila por marca; la publicación exige `expected_draft_id` y reintentos/carreras se mapean de forma determinista (reintento idempotente o 409 con detalles), sin duplicar versiones.
- Semántica de Knowledge según `WORKFLOWS.md` sin sincronización: crear o editar un borrador marca la versión `ACTIVE` vigente `SYNCED` como `OUTDATED`; publicar crea la nueva versión con `NOT_SYNCED`; ninguna acción inicia sincronización.
- Envelope de error centralizado `{error: {code, message, details}}` para toda respuesta de error de la API — 401/403/404/409/422/503 con códigos exactos (`SERVICE_UNAVAILABLE` cubre los 503 actuales de health readiness sin base de datos y auth sin configurar) — generado en manejadores compartidos que traducen `HTTPException`, validación de request y errores de dominio, aplicado también a los endpoints de identidad y health existentes.
- Frontend: integración Dashboard <-> Brand DNA (panel de estado azul profundo y CTA de onboarding en vacío), superficie Brand DNA (navegación de secciones, edición de borrador, publicación, versiones) y superficie Create Brand DNA (autoría estructurada manual).
- Estados de datos, API, error y permiso en cada superficie nueva; requisitos responsivos, de foco y de movimiento según la referencia visual fluffy.
- Autenticación de desarrollo mediante mapping local ignorado rol/perfil -> token de vida corta: el shell autentica solo tras `GET /api/v1/me`, deriva identidad y rol únicamente de esa respuesta, invalida las queries de marca al cambiar de identidad y permanece anónimo ante tokens inválidos o ausentes; el token nunca se registra ni se commitea. El login productivo con Supabase sigue siendo una change separada.
- Seeds de la marca demo `Kinu` y sus membresías como datos de seed del backend, no constantes del frontend.

Fuera de alcance (changes posteriores, nunca alcance accidental): generación AI del DNA (endpoint `generate`), sincronización de Brand Knowledge/RAG, Creative Studio, Approvals, Brand Audit/Visual Audit, Observability/Langfuse, y login productivo con Supabase. La navegación del starter se conserva completa; las secciones fuera de alcance permanecen deshabilitadas como en la foundation.

## Capabilities

### New Capabilities

- `brand-dna`: Autoría estructurada con contrato canónico, contratos de lectura por rol, versionado, publicación inmutable, concurrente e idempotente, envelope de error centralizado y semántica de estado de Knowledge sin ejecutar la sincronización.

### Modified Capabilities

- Ninguna. `openspec/specs/` aún no contiene capabilities aceptadas; esta change no modifica requirements de la change de foundation.

## Impact

- `apps/api`: nuevo módulo `brand_dna` (router, service, repository, policies, schemas), migración Alembic, seeds, tests pytest y manejadores de error centralizados compartidos; reutiliza `identity` (dependencia de auth y políticas) adaptando solo la forma de sus respuestas de error al envelope.
- `apps/web`: nuevas rutas y superficies Brand DNA + Create Brand DNA, integración del panel de estado en Dashboard, cliente API autenticado para desarrollo; nuevas dependencias de formulario (React Hook Form + Zod) a validar con Context7 durante la implementación.
- No se introducen provider SDKs en routers, no se añade IA ni RAG, no se cambia la estrategia de auth productiva ni el estado de workflow de creative (inexistente aquí).
- Supone deuda conocida heredada: el round-trip de migración sobre PostgreSQL/Supabase real sigue pendiente de verificarse en un entorno seguro.
