## Context

Identity ya resuelve usuario autenticado, membresía de marca y rol (`authorize_brand_action` → `PermissionDeniedError` → 403 con envelope centralizado en `errors.py`), y Brand DNA ya fija el patrón de transición inválida → `InvalidWorkflowTransitionError` → 409 con claim condicional atómico y transacciones cortas comprometidas antes de cualquier `await` (change 006). La change paralela `008-creative-studio` define `creative_items`/`creative_versions` versionadas inmutables con brief, output, contexto aplicado, score y trace persistidos por versión. No existe `openspec/specs/` archivado: esta change introduce la capability `content-governance`. Ver `proposal.md` (Why) y `specs/content-governance/spec.md` (requisitos); este documento solo fija el cómo.

## Goals / Non-Goals

**Goals:**

- Transiciones de revisión semántica, decisiones y eventos siempre atómicos por transacción de base de datos.
- Idempotencia de decisiones sin infraestructura extra (sin idempotency keys ni colas).
- Reutilizar los patrones ya probados del repo: membership-first, claim condicional sobre columna de estado, envelope de errores, enum + índices Alembic reversibles.
- Superficies frontend role-gated con server state real (cola, detalle congelado, timeline) y cero capacidades de edición para revisores.

**Non-Goals:**

- Estados visuales (`PENDING_VISUAL_REVIEW`, `VISUAL_CHANGES_REQUESTED`, `FINAL_APPROVED`): spec 06 los añade a su propio enum aditivamente.
- Workflows configurables, notificaciones, SLA de cola, paginación de history.
- Cualquier llamada a IA o retrieval al decidir: solo evidencia ya persistida.
- Protección RLS a nivel de base de datos: pertenece al eje 007.

## Decisions

### Módulo `governance` dueño de la máquina de estados y seam con 008

El módulo `apps/api/app/governance` (models, repository, policies, service, router, schemas) es la única autoridad de `workflow_status` y de las tablas `content_reviews`/`workflow_events`. El endpoint `POST /api/v1/creative-items/{item_id}/submit` (ruta de Creative en `API.md`) delega al service de governance: la semántica de submit (congelar referencia + transición + evento) es de esta change, mientras que la creación/generación/versionado pertenece a 008. Spec 05 asigna explícitamente "añadir workflow_status en creative_items" a esta change; la tarea de migración verifica primero el estado final de la migración de 008 para no duplicar columna ni enum (si 008 ya creó la columna por defecto `DRAFT`, esta change solo crea las tablas nuevas y los índices de cola). El enum se nombra `creative_workflow_status` con exactamente `DRAFT | PENDING_CONTENT_REVIEW | CONTENT_CHANGES_REQUESTED | CONTENT_APPROVED`.

### Comandos transaccionales sin `await` y claim condicional atómico

Submit, approve y request-changes ejecutan en una única transacción de base de datos: (1) claim condicional `UPDATE creative_items SET workflow_status = :dest WHERE id = :id AND workflow_status = :expected` (rowcount 0 → releer y responder idempotente o 409 según dirección), (2) `INSERT content_reviews` (solo decisiones), (3) `INSERT workflow_events`. Sin llamadas a proveedores ni I/O externo dentro de la transacción: el patrón 006 de "transacciones cortas comprometidas antes de cualquier `await`" se reduce aquí a "no hay `await`". Alternativa rechazada: dos fases con relectura optimista — duplica superficie de error sin ganancia, los comandos no tienen efectos externos que compensar.

### Orden de guards: membership-first consistente

403 por membresía → 404 por recurso inexistente (con membresía) → 403 por rol → 409 por estado inválido → validación de payload. El 403 de membresía se evalúa antes de resolver el recurso (no filtra 404 vs 403 por existencia ajena), igual que Knowledge en 006. El rol se valida con la membresía ya resuelta server-side; el cliente nunca envía rol ni estado.

### Idempotencia por estado con read-back, sin idempotency keys

Tras perder el claim (rowcount 0), el service relee el estado: si la decisión persistida sobre la versión enviada tiene la misma dirección, responde el resultado vigente (200 con el recurso); si es dirección contraria o el estado no admite el comando, 409. El claim garantiza un solo ganador concurrente; no hay efectos externos que exigir claves de idempotencia (decisión de YAGNI documentada). La constraint `UNIQUE (creative_item_id, submitted_version_id, decision)` queda como red de seguridad en base de datos ante cualquier carrera no capturada: la lógica de dominio nunca depende de ella.

### Congelación por referencia, sin flags en `creative_versions`

La inmutabilidad de la versión ya es invariante de 008 (versiones append-only). Congelar = fijar `submitted_version_id` en la decisión/cola y exigir versión de número mayor en cada reenvío desde `CONTENT_CHANGES_REQUESTED`. No se añaden columnas de estado a `creative_versions`: menos superficie, misma garantía.

### Cola como read model determinista

La cola consulta ítems `PENDING_CONTENT_REVIEW` de las marcas con membresía `CONTENT_REVIEWER`, ordenados por el timestamp del evento `SUBMITTED` más reciente del ítem (ASC) con desempate `id` ASC — reproducible en PostgreSQL y SQLite. Índice `(creative_item_id, created_at DESC)` en `workflow_events` mantiene el coste del "evento más reciente" bajo; a escala demo el agregado por ítem es aceptable y se reemplaza por una columna desnormalizada solo si se vuelve medible.

### Eventos append-only a nivel de aplicación

`workflow_events` solo tiene rutas de inserción y lectura en el repositorio de dominio; no se exponen endpoints de mutación. Tipos canónicos: `SUBMITTED`, `CONTENT_APPROVED`, `CONTENT_CHANGES_REQUESTED` (texto, extensibles aditivamente). La metadata referencia versión y decisión por id — nunca output ni datos sensibles. El trace de generación se muestra por referencia al `langfuse_trace_id` ya persistido en la versión.

### Contratos API

`GET /content-reviews/queue` (lista con marca, tipo, título, versión enviada resumida, entrada a la cola), `GET /content-reviews/{item_id}` (versión congelada completa + contexto aplicado persistido + feedback previo + estado), `POST /content-reviews/{item_id}/approve` (sin body), `POST /content-reviews/{item_id}/request-changes` (body `{feedback}` obligatorio, 422 con envelope), `GET /content-reviews/{item_id}/history` (eventos ASC). Schemas Pydantic estrictos (`extra="forbid"`), UUIDs y UTC. Lecturas permitidas al Creator de sus ítems (detalle y history) para la vista de estado/feedback; la cola es del reviewer.

### Frontend

Feature `apps/web/src/features/approvals`: ruta `/approvals` conectada solo en el nav de `CONTENT_REVIEWER` (nav.ts), cola con estados reales de carga/vacío/error, detalle de versión congelada en superficie editorial densa (clay tenue, contraste AA), approve/request-changes con formulario de feedback validado (React Hook Form + Zod, patrón existente) y timeline append-only. En Creative Studio, el Creator ve estado del ítem y feedback de decisiones (misma fuente del detalle de revisión) sin controles sobre la versión enviada. Server state con TanStack Query (patrón existente); sin Redux ni estado optimista en decisiones (un retry debe reflejar exactamente el resultado del backend).

### Tests por invariante, no por ruta

Suite nueva `apps/api/tests/test_governance_*.py` sobre SQLite real con las fixtures existentes: happy path submit→changes→nueva versión→resubmit→approve; 403 Creator/Visual/membresía; 409 estados inválidos y reenvío de la misma versión; idempotencia secuencial y claim concurrente (dos corridas del command sobre el mismo ítem esperado → una decisión); history ordenado y append-only; aislamiento de cola entre marcas; API queue/detalle/decisiones/history. Frontend: tests mínimos de gating de rol y render de estados (patrón de las features existentes).

## Risks / Trade-offs

- [Seam con 008 sobre submit y la columna workflow_status] → la tarea de migración verifica la migración de 008 antes de escribir la propia; si 008 creó la columna/enum, esta change los reutiliza y solo añade tablas e índices. Cualquier duplicación se detecta en `alembic upgrade head`.
- [Colisión de numeración con changes paralelas en vuelo (`008-visual-compliance`, `009-observability-facade`)] → es un problema de nombres de directorio, no de contenido; el orquestador renombra antes de archivar. Registrado aquí para que no se pierda.
- [Agregado "evento SUBMITTED más reciente" en la cola] → coste O(eventos por ítem) acotado por índice; desnormalizar solo con evidencia de lentitud medible.
- [Enum cerrado a 4 estados] → spec 06 añade estados visuales con `ALTER TYPE ... ADD VALUE` en su propia change; no pre-declarar (YAGNI).
- [Append-only sin RLS] → la protección es de aplicación (repositorio sin rutas de mutación); el endurecimiento a nivel de fila pertenece al eje 007 y puede extenderse a estas tablas después.

## Migration Plan

1. Migración Alembic reversible (nueva revisión tras la cabeza vigente, verificando la cadena contra las migraciones paralelas en vuelo): `upgrade` crea `content_reviews` (con FK a item, versión enviada, reviewer y constraint UNIQUE de seguridad), `workflow_events` (con índice item+created_at) y añade `creative_items.workflow_status` con default `DRAFT` si 008 no la creó; `downgrade` elimina tablas y columna en orden inverso.
2. Registro del módulo en `alembic/env.py`, router en `main.py` y handlers de errores de governance en `errors.py`.
3. Round-trip de verificación sobre SQLite: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`.
4. Rollback de aplicación: revert del deploy; los datos de decisiones/eventos son derivables de las decisiones ya tomadas, no hay reconstrucción pendiente.
