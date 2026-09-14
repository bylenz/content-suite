## Why

Creative Studio (spec 04) permite al Creator crear, versionar y generar contenido, pero la decisión semántica humana no existe: no hay `content_reviews`, `workflow_events`, endpoints de Content Review ni UI de reviewer, y el workflow muere sin salida de `PENDING_CONTENT_REVIEW`. La regla "el Creator no puede aprobar su propio contenido" ya vive en Identity, pero no hay superficie que la ejerza. Sin esta capa se rompen las invariantes de producto "las decisiones de aprobación son humanas", "cada artefacto importante es versionado" y "workflow history append-only".

## What Changes

- Nuevo módulo `apps/api/app/governance` dueño de la máquina de estados de revisión semántica sobre `creative_items`: `DRAFT → PENDING_CONTENT_REVIEW → (CONTENT_CHANGES_REQUESTED → PENDING_CONTENT_REVIEW)* → CONTENT_APPROVED`, con transiciones protegidas solo en backend.
- Migración reversible que crea `content_reviews` y `workflow_events`, añade `workflow_status` (enum `creative_workflow_status`, default `DRAFT`) a `creative_items` con índice de cola, y constraints/índices de item, versión enviada y timestamps según `DATA_MODEL.md`.
- El comando `POST /api/v1/creative-items/{item_id}/submit` pertenece a esta change: congela la versión exacta (`submitted_version_id`), exige versión nueva distinta en cada reenvío desde `CONTENT_CHANGES_REQUESTED`, transiciona a `PENDING_CONTENT_REVIEW` y registra el `workflow_event` en la misma transacción.
- Servicio transaccional para queue, detalle, approve y request-changes: transición de estado + decisión en `content_reviews` + `workflow_event` se comprometen juntos o nada; guards de rol (`CONTENT_REVIEWER` para decidir; 403 para Creator y Visual Reviewer), de estado (solo desde `PENDING_CONTENT_REVIEW`; 409 en el resto) y de brand membership en cada command.
- Idempotencia de decisiones: reintentar approve/request-changes sobre un ítem ya decidido en la misma dirección devuelve el resultado vigente sin duplicar decisiones ni eventos; decidir en dirección contraria sobre la misma versión enviada responde 409 sin transición.
- Endpoints Content Review de `API.md` (`GET /content-reviews/queue`, `GET /content-reviews/{item_id}`, `POST /content-reviews/{item_id}/approve`, `POST /content-reviews/{item_id}/request-changes`, `GET /content-reviews/{item_id}/history`) con envelopes de error existentes (403 rol, 404 membership+recurso, 409 transición).
- Frontend: activar la navegación `/approvals` solo para Content Reviewer con cola, detalle de versión congelada, contexto aplicado ya persistido, approve/request-changes con feedback y timeline append-only; el Creator observa estado y feedback del ítem en Creative Studio sin editar la versión enviada.
- Las decisiones no invocan IA: solo presentan evidence/context ya persistido por Creative; el trace original de generación se vincula por referencia.
- Observabilidad de dominio: cada decisión y transición queda como `workflow_event` con actor, tipo de evento, metadata sanitizada y timestamp; history es append-only.

## Capabilities

### New Capabilities
- `content-governance`: revisión semántica humana de Creative con máquina de estados protegida (`DRAFT`, `PENDING_CONTENT_REVIEW`, `CONTENT_CHANGES_REQUESTED`, `CONTENT_APPROVED`), submit de versión exacta congelada, cola real para Content Reviewer, decisiones inmutables que referencian la versión enviada, idempotencia de decisiones e history append-only con actor/evento/tiempo.

### Modified Capabilities
- Ninguna (`openspec/specs/` aún no archiva capabilities; el contrato creative del que dependen estos requisitos lo introduce la change `008-creative-studio` y no se modifica aquí).

## Impact

- `apps/api`: nuevo módulo `governance` (models, repository, policies, service transaccional, router, schemas); migración Alembic nueva (`content_reviews`, `workflow_events`, `creative_items.workflow_status` + índices); registro en `alembic/env.py`, router en `main.py` y handlers de errores en `errors.py`; tests nuevos (service por invariante + API + idempotencia).
- Dependencia dura de `008-creative-studio`: `creative_items`/`creative_versions`, applied context persistido y versión enviada inmutable. Se asume que 008 crea el ítem en `DRAFT`; si 008 llegara a exponer un `submit` propio, esta change lo reemplaza con el comando transaccional descrito aquí (seam a coordinar entre ambas changes antes de implementar).
- `apps/web`: feature `approvals` (cola, detalle congelado, decisiones, timeline) activa para `CONTENT_REVIEWER`; estado y feedback visibles para el Creator en la superficie de Creative Studio; ruta `/approvals` conectada a `nav.ts`.
- Sin cambios en: Brand DNA/Knowledge, AI Platform (ninguna llamada a modelos al decidir), Visual Audit (spec 06), roles de Identity.
