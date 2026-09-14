# Objective

Implementar la revisión semántica humana de Creative con una máquina de estados protegida, cola real, decisiones inmutables y workflow history append-only.

# Current State

Creative llega de la spec 04; no existen `content_reviews`, `workflow_events`, endpoints Approvals ni UI de reviewer. Los roles y la regla de que Creator no aprueba están implementados en Identity.

# In Scope

- Extender workflow de Creative con DRAFT, PENDING_CONTENT_REVIEW, CONTENT_CHANGES_REQUESTED y CONTENT_APPROVED.
- Tablas `content_reviews` y `workflow_events`; decisiones referencian la versión exacta enviada.
- Servicio transaccional para submit, queue, approve, request changes e history, con guards de rol/current state/idempotencia.
- UI de Approvals para Content Reviewer: cola, detalle de versión congelada, contexto aplicado, approve/request changes y timeline.
- UI Creator para ver estado y feedback; no editar directamente la versión enviada.

# Out of Scope

- Visual asset, audit multimodal, final approval, configurabilidad de workflows y cambios de contenido por reviewer.

# Domain / Modules Affected

`creative`, nuevo módulo `governance`, Identity RBAC, frontend Approvals y Dashboard solo para estado respaldado.

# Database Changes

Crear `content_reviews` y `workflow_events`; añadir workflow_status en creative_items y constraints/índices de item, version y timestamps.

# API Changes

Implementar cola, detalle, approve, request-changes e history de Content Review descritos en `API.md`; usar 403 para rol, 409 para estado inválido e idempotencia en decisiones.

# Frontend Changes

Activar Approvals únicamente para Content Reviewer; Creator observa estado/feedback. Preservar sidebar y materialidad aprobadas.

# AI / RAG Changes

Sólo presenta evidence/context ya persistido; no genera ni vuelve a consultar modelos al decidir.

# Security / RBAC Requirements

El Creator no puede aprobar su contenido. Reviewer no edita ni altera una versión. Validar brand ownership y versión enviada en cada command.

# Observability Requirements

Registrar decisiones y transiciones como eventos de dominio; vincular trace original de generación sólo como referencia, sin duplicar datos sensibles.

# Acceptance Criteria

- Submit congela la versión exacta y crea event.
- Approve/request changes sólo funciona para Content Reviewer y desde PENDING_CONTENT_REVIEW.
- Request changes exige nueva versión para reenvío.
- History es append-only y refleja actor, evento y tiempo.

# Tests Required

Happy path submit→changes→new version→resubmit→approve; permisos inválidos; transiciones 409; retry/idempotencia; API queue/history y UI state básico.

# Manual Verification Steps

Alternar Creator/Content Reviewer con tokens de dev y completar el ciclo semántico; comprobar que las decisiones no cambian el output enviado.

# Stop Condition

Detener si una transición se confía al frontend, se sobrescribe versión enviada o reviewer obtiene capacidades de edición.
