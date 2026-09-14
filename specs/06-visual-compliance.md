# Objective

Implementar versionado de visuales, Storage privado, auditoría multimodal basada en Brand Knowledge y decisión final humana.

# Current State

No existen modelos, storage abstraction, rutas, UI ni auditoría Visual. Creative debe estar CONTENT_APPROVED y Brand Knowledge visual disponible antes de iniciar esta spec.

# In Scope

- Puerto de Storage privado, validación de archivo/tamaño/tipo y signed URLs de corta duración.
- `visual_assets`, `visual_audits` y `visual_reviews`, con versiones inmutables, findings estructurados, score determinista y workflow events.
- Upload de visual ligado al creative item aprobado; audit vía VisionModel con contexto visual mandatory/semántico; decisiones approve/request changes y excepción HIGH explícita.
- UI para Creator upload/estado y Visual Compliance Reviewer queue, asset, findings/evidencia, historial y decisión.

# Out of Scope

- Generación de imágenes, editor gráfico, bucket público, revisión configurable, aprobación automática por score.

# Domain / Modules Affected

Nuevos módulos `storage` y `visual_audit`; `creative`, `knowledge`, `ai`, `governance`, frontend Brand Audit.

# Database Changes

Crear tablas del modelo de datos para visual assets/audits/reviews, enums, FKs a creative/version Brand DNA y auditorías; usar migraciones reversibles.

# API Changes

Implementar endpoints de visual assets/audit/review/history de `API.md`, contratos Pydantic de findings y envelopes 403/404/409/422/503.

# Frontend Changes

Activar Brand Audit sólo para rutas/roles listos; usar signed URL tras validación, no storage paths. Mostrar estados, findings y excepciones reales; conservar el lenguaje visual de starter-design.

# AI / RAG Changes

VisionModel sólo se invoca desde capability/service; context builder visual exige reglas mandatory. Findings siguen contrato `rule_id/category/severity/status/expected/detected/evidence/recommendation`; backend calcula score y no aprueba automáticamente.

# Security / RBAC Requirements

Storage privado, validación server-side, membership/resource-brand checks, signed URLs, reviewer visual no modifica DNA/contenido y cada excepción HIGH queda auditada.

# Observability Requirements

Trazar upload/audit con versión visual, Brand DNA, modelo/prompt, latencia, resultado estructurado y error sanitizado.

# Acceptance Criteria

- Un visual auditado nunca se sobrescribe: una corrección crea nueva versión.
- Audit falla seguro sin Knowledge visual obligatorio.
- Sólo Visual Compliance Reviewer decide la aprobación final.
- Aprobación con HIGH requiere `exception_accepted=true` y evidencia persistida.

# Tests Required

Storage fake, validación de archivo, URL autorizada, RBAC, workflow states, score determinista, findings Pydantic, falta de Knowledge, migraciones y API integration.

# Manual Verification Steps

Completar CONTENT_APPROVED, cargar visual permitido, ejecutar audit fake, pedir cambios, cargar nueva versión y aprobar como Visual Reviewer; probar rechazo de archivo/no membership.

# Stop Condition

Detener si un objeto se hace público por defecto, score decide automáticamente, audit omite Knowledge o versiones auditadas se mutan.
