## Context

Ver `proposal.md` y `specs/brand-dna/spec.md`. La foundation entregó: módulo `identity` con frontera JWT (HS256 con `iss`/`aud`/`exp` verificados), políticas de membresía (`authorize_brand_action`), migración inicial de `profiles`/`brands`/`brand_memberships`, shell web con boundary de sesión demo (presentación), cliente API y tokens clay sobre la paleta canónica. `/api/v1/me` ya resuelve membresías server-side con `brand_id`, `brand_slug` y `role`. No existen módulos de negocio, ni AI, ni RAG. La autoridad visual es la referencia fluffy suministrada junto con `starter-design/Content Suite.dc.html` (superficies Brand DNA, Create Brand DNA y tarjetas de estado del Dashboard).

## Goals / Non-Goals

**Goals:**

- Entregar la primera capability de producto con la layering existente del monolito, sin excepciones a las reglas de arquitectura.
- Hacer que la web consuma la API real autenticada en desarrollo, manteniendo la autoridad de roles en el backend.
- Definir semántica completa de versiones y de `knowledge_status` aunque la sincronización no exista todavía.

**Non-Goals:**

- No implementar `POST /brand-dna/generate` (AI), Knowledge/RAG, Creative Studio, Approvals, Visual Audit, Observability ni login productivo con Supabase.
- No implementar Brand Assets ni Storage: quedan excluidos y pertenecen a una change futura de Brand DNA/Storage. Visual Audit es únicamente consumidor de esos assets, nunca su dueño.
- No introducir colas, workers ni procesos asíncronos; la publicación es transaccional y síncrona.

## Decisions

### Módulo `brand_dna` con la layering del monolito
Estructura idéntica a `identity`: `router.py` (sin SQL, sin SDKs) -> `service.py` (transiciones y transacción de publicación) -> `repository.py` (SQLAlchemy) + `policies.py` reutilizando `authorize_brand_action` de identity. La escritura exige membresía con rol `CREATOR`; la lectura, cualquier membresía. El rol nunca se toma del cliente.

Alternativa descartada: autorización inline en el router. Repite la política por endpoint y la saca del dominio.

### Contratos de lectura y matriz RBAC
El rol se resuelve siempre desde la membresía persistida; sin membresía el 403 se responde antes de evaluar el recurso. Matriz de visibilidad:

| Recurso | CREATOR | CONTENT_REVIEWER / VISUAL_REVIEWER | Sin membresía |
|---|---|---|---|
| `GET /brand-dna` -> `active` | sí | sí | 403 |
| `GET /brand-dna` -> `draft` | recurso completo con documento | `null` (nunca se entrega recurso, metadato ni contenido del borrador) | 403 |
| `GET /versions` (lista) | incluye la entrada `DRAFT` | excluye toda entrada `DRAFT` | 403 |
| `GET /versions/{version}` publicada | sí | sí | 403 |
| `GET /versions/{version}` en `DRAFT` | sí | 404 (no confirma existencia) | 403 |

Ninguna respuesta hacia revisores contiene id, número de versión, conteos, metadatos, documento ni recurso alguno de un `DRAFT`; el 404 en el detalle de una versión `DRAFT` no confirma su existencia. Como excepción explícita, el `knowledge_status = OUTDATED` de la versión `ACTIVE` puede comunicar de forma genérica que hay cambios pendientes de publicación: ese estado pertenece a la propia versión activa y es permisible, pero no prueba, nombra ni identifica un borrador.

Alternativa descartada: responder 403 en el detalle de versión `DRAFT`. Confirmaría a un revisor que la versión existe.

### Envelope de error centralizado
Manejadores de excepción a nivel de app (módulo compartido de `apps/api/app`) producen el envelope único `{error: {code, message, details}}` para toda respuesta de error de la API, traduciendo tres fuentes: (a) `HTTPException` de FastAPI —incluidos los endpoints de identidad y health existentes, cuyo `detail` plano queda reemplazado por la forma canónica—, (b) excepciones de validación de request (`RequestValidationError`, Pydantic) y (c) errores de dominio (`PermissionDeniedError`, errores de transición). Códigos exactos: 401 `UNAUTHENTICATED` (identidad ausente/inválida, `details: {}`, conserva la cabecera `WWW-Authenticate`), 403 `PERMISSION_DENIED` (sin membresía o rol insuficiente), 404 `NOT_FOUND` (recurso inexistente, ruta desconocida o no visible por rol), 409 `INVALID_WORKFLOW_TRANSITION` (transición inválida o conflicto de publicación; `details` p. ej. `{expected_draft_id, active_version_id}`), 422 `VALIDATION_ERROR` (`details` con las rutas de campo inválidas) y 503 `SERVICE_UNAVAILABLE` (dependencia esencial no disponible). Los dos casos 503 actuales de la aplicación quedan cubiertos por esta política: `/health/ready` con base de datos inalcanzable y la frontera de auth sin configurar; ambos son `HTTPException` traducidas por el mismo manejador. `details` es `{}` cuando el código no tiene detalles adicionales.

Alternativa descartada: envelope por módulo. Duplicaría la forma y dejaría divergencias entre `identity` y `brand_dna`.

### Modelo de datos y migración
Tabla `brand_dna_versions` exactamente como `DATA_MODEL.md` (uuid PK, `brand_id` FK, `version int`, `status` enum `DRAFT/ACTIVE/ARCHIVED`, `document jsonb`, `created_by`, `created_at`, `published_at`, `knowledge_status` enum `NOT_SYNCED/SYNCING/SYNCED/OUTDATED/FAILED`, `UNIQUE(brand_id, version)`), más dos invariantes a nivel de base: índice único parcial por marca `WHERE status = 'DRAFT'` y `WHERE status = 'ACTIVE'`. Motor síncrono y migración portable (SQLite para tests, `postgresql+psycopg` para Supabase), continuando el criterio de la foundation.

Alternativa descartada: invariantes solo en el servicio. La base protege la inmutabilidad del versionado ante concurrencia y bugs.

### Contrato canónico del documento
El documento es un JSON estricto de cinco secciones; Pydantic (`extra="forbid"`) en backend y Zod (esquema espejo `.strict()`) en frontend comparten esta definición. Todo string se recorta antes de validar y persistir; un string vacío tras el recorte es inválido. Límites: 1..500 por campo narrativo corto, 1..1000 por guía extendida, 1..60 por etiqueta de lista, 1..300 por regla/ejemplo, 1..80 por nombre de pilar; tamaño serializado máximo 32 KiB.

| Sección | Campo | Tipo | Cardinalidad / límite |
|---|---|---|---|
| identity | purpose | string | 1..500 |
| identity | positioning | string | 1..500 |
| identity | personality_traits | string[] | 1..8 items de 1..60 |
| identity | audience | string | 1..500 |
| voice | tone_characteristics | string[] | 1..8 items de 1..60 |
| voice | usage_guide | string | 1..1000 |
| voice | preferred_vocabulary | string[] | 0..30 items de 1..60 |
| voice | avoid_vocabulary | string[] | 0..30 items de 1..60 |
| voice | do_examples | string[] | 1..10 items de 1..300 |
| voice | dont_examples | string[] | 1..10 items de 1..300 |
| communication | message_pillars | {name 1..80, description 1..300}[] | 1..5 items |
| communication | rules | string[] | 1..20 items de 1..300 |
| visual_rules | visual_personality | string | 1..500 |
| visual_rules | imagery_direction | string | 1..500 |
| visual_rules | composition | string | 1..500 |
| visual_rules | logo_usage | string | 1..500 |
| restrictions | rules | string[] | 1..20 items de 1..300 |

Política de campos desconocidos: cualquier sección, campo o clave extra se rechaza con 422 `VALIDATION_ERROR` y `details` enumera las rutas ofensivas. Mapeo con el starter: Brand Core (con audiencia) -> `identity`; Tone of Voice -> `voice`; Messaging + reglas ALWAYS -> `communication`; Visual Guidelines -> `visual_rules`; reglas NEVER -> `restrictions`. Los conteos por sección se derivan del documento (sin contadores desnormalizados). Brand Assets no forma parte del documento en esta change.

Formas de request/response:
- `PATCH /brands/{brand_id}/brand-dna/draft` body `{"document": <documento canónico>}`: reemplazo completo del documento del borrador (no merge parcial), idempotente en contenido.
- Recurso de versión: `{id, brand_id, version, status, document, created_by, created_at, published_at, knowledge_status, section_counts}`; el `document` completo se entrega en `GET /brand-dna` y en `GET /versions/{version}`; la lista de versiones devuelve el recurso sin `document`.
- `GET /brands/{brand_id}/brand-dna` -> `{"active": <recurso|null>, "draft": <recurso|null>}` según la matriz RBAC.

Alternativa descartada: secciones libres tipo markdown blob. Rompe el requisito de documento operativo estructurado y la futura derivación de chunks.

### Semántica de versiones y publicación transaccional
`version = max(version) + 1`. Editar sin borrador crea el siguiente `DRAFT` inicializado con el documento de la `ACTIVE` vigente; si ya existe `DRAFT`, se actualiza in place. `ACTIVE` y `ARCHIVED` jamás reciben UPDATE de documento. La fila del borrador es la que transiciona a `ACTIVE` (conserva su `id`), lo que hace determinista el reintento.

Mutación del borrador (`PATCH /draft`): misma transacción con `SELECT ... FOR UPDATE` sobre la fila de `brands`, adquirida antes de calcular `max(version) + 1`, crear o actualizar el borrador y aplicar la transición `SYNCED -> OUTDATED` de la activa. Si una carrera escapara al bloqueo y disparara `IntegrityError` (por `UNIQUE(brand_id, version)` o el índice único parcial de `DRAFT`), la recuperación es determinista: rollback, relectura bajo bloqueo en transacción nueva y reaplicación del upsert; nunca 5xx.

Publicación — `POST /publish`, body `{"expected_draft_id": "<uuid>"}` (campo requerido):
1. Transacción con secuencia obligatoria: `SELECT ... FOR UPDATE` sobre la fila de `brands` (serializa mutaciones por marca en PostgreSQL) -> leer `DRAFT` y `ACTIVE` -> validar -> `ACTIVE` previa `-> ARCHIVED` + flush (libera el índice único parcial de `ACTIVE` antes de crear la nueva) -> `DRAFT -> ACTIVE` + `published_at` + `knowledge_status = NOT_SYNCED` -> flush + commit.
2. Mapeo determinista de carreras, evaluado tras adquirir el bloqueo: sin `DRAFT`, si la `ACTIVE` vigente tiene `id == expected_draft_id` -> reintento idempotente (200 con la versión activa, sin duplicar); si no coincide -> 409 `INVALID_WORKFLOW_TRANSITION` con `details {expected_draft_id, active_version_id}`; sin `DRAFT` y sin versiones -> 409. Con `DRAFT` presente pero `id != expected_draft_id` -> 409 (UI desactualizada).
3. Defensa ante `IntegrityError` del índice único parcial `ACTIVE` (carrera que escapara al lock): rollback, relectura en transacción nueva y aplicación del mismo mapeo; nunca 5xx.
4. Reintento del cliente: seguro por diseño; `UNIQUE(brand_id, version)` y los índices únicos parciales impiden versiones duplicadas y doble `ACTIVE`.

Alternativas descartadas: publicar creando fila nueva fuera de transacción (permite dos `ACTIVE` observables); idempotencia por `Idempotency-Key` header (requiere almacenar claves; `expected_draft_id` ya identifica la operación de forma determinista).

### `knowledge_status` según WORKFLOWS, sin sincronización
Se aplican solo los tramos del ciclo de `WORKFLOWS.md` que no requieren sincronizar: crear o editar un `DRAFT` transiciona la `ACTIVE` vigente de `SYNCED` a `OUTDATED` (los demás estados de la `ACTIVE` quedan intactos; idempotente ante ediciones repetidas del borrador); publicar crea la nueva `ACTIVE` con `NOT_SYNCED` y la versión archivada conserva el estado que tenía. Ninguna acción de esta capability inicia `SYNCING` ni produce `SYNCED`/`FAILED`: esas transiciones pertenecen a la capability Knowledge. La UI presenta el estado real ("pendiente de sincronización" / "desactualizado: hay cambios pendientes") sin simular una sincronización inexistente y sin afirmar que exista un borrador.

### Seeds demo reproducibles
Script de seeds ejecutable con `uv run` que crea (idempotentemente) marca `Kinu`, perfiles demo y membresías por rol. El nombre del workspace y los avatares del frontend permanecen como presentación; todo dato de dominio proviene de la API.

Alternativa descartada: fixtures en tests solamente. La demo y el desarrollo local necesitarían datos manualmente.

### Frontend: superficies, server state y formularios
Rutas: `/brand-dna` (vista del documento con navegación de secciones Overview + cinco secciones + Versiones, edición de borrador, publicación) y `/brand-dna/create` (autoría estructurada). El Dashboard añade el panel de estado azul profundo con badge de estado, conteos y estado de Knowledge, y el CTA de onboarding cuando no hay versión publicada. El `brand_id` se resuelve desde `/api/v1/me` (membresía del workspace), sin nueva autoridad de sesión. Server state con TanStack Query (queries + invalidaciones tras publish); el formulario de autoría usa React Hook Form + Zod, dependencias a validar con Context7 al instalar. Materialidad según la referencia fluffy y `docs/UI_UX.md`: clay claro y suave en tarjetas elevadas de radio amplio, relieve reducido en el documento editorial denso, tiles pastel para métricas semánticas, CTA Steel, foco visible con contraste >= 3:1, `prefers-reduced-motion`, y las secciones del starter fuera de alcance permanecen deshabilitadas.

Alternativa descartada: formularios controlados a mano. El documento tiene ~20 campos en cinco secciones; RHF+Zod es el estándar fijado por AGENTS para este caso.

### Autenticación de desarrollo: mapping local rol/perfil -> token de vida corta
Frontera exacta: el login productivo con Supabase sigue fuera de alcance; en desarrollo, un script Python (`uv run`) acuña, para cada perfil seed, un JWT HS256 de vida corta (p. ej. 15 minutos, con `iss`/`aud`/`exp` verificables por la frontera existente) usando solo el secreto local de dev, y escribe el mapping rol -> token en `apps/web/.env.development.local` (ignorado por Git, cargado por Vite solo en modo development): `VITE_DEV_API_TOKEN_CREATOR`, `VITE_DEV_API_TOKEN_CONTENT_REVIEWER`, `VITE_DEV_API_TOKEN_VISUAL_REVIEWER`. El conmutador de rol demo únicamente selecciona qué entrada del mapping se adjunta, y solo en builds de desarrollo (`import.meta.env.DEV`).

Reglas del shell: la sesión se autentica exclusivamente tras un `GET /api/v1/me` 200 con el token seleccionado; la identidad y el rol mostrados provienen solo de esa respuesta; un token inválido, ausente o expiado deja la sesión anónima (estado de no autenticado, nunca un rol demostrativo); al cambiar de identidad se invalidan todas las queries de marca (limpieza del cache de TanStack Query) antes de reautenticar. El token nunca se registra en logs ni consola y jamás se commitea; los builds de producción no incluyen rutas de código que lean el mapping.

Alternativas descartadas: token único fijo en `.env.local` (no representa los tres roles y acopla la UI a una sola identidad); mockear los datos en la web (contradice la fuente de verdad en la base y dejaría la capability sin verificación real de permisos).

### Qué queda (visión por fases)
Esta change entrega la fase de autoría del DNA. Fases posteriores sugeridas, ninguna iniciada aquí:
1. `003-knowledge-sync`: módulo Knowledge, chunks, embeddings y transiciones reales de `knowledge_status`.
2. Creative Studio: creative items/versiones, generación AI sobre Brand Knowledge, consistency check.
3. Approvals/Governance: cola de revisión y workflow de contenido.
4. Brand Assets/Storage y Visual Audit: la change de Storage introduce los assets del Brand DNA; Visual Audit únicamente los consume para auditoría multimodal y decisión visual.
5. Observability: tracing Langfuse y facade de traces.
6. Login productivo con Supabase y endurecimiento de deployment (incluye resolver la deuda del round-trip de migración sobre PostgreSQL/Supabase real heredada de la foundation).

## Risks / Trade-offs

- [La UI puede sugerir una sincronización inexistente o insinuar borradores a revisores] → Copys honestos con `NOT_SYNCED` ("pendiente de sincronización") y `OUTDATED` ("desactualizado: hay cambios pendientes"), sin señales de éxito de sincronización y sin afirmar la existencia de un borrador; escenarios spec que lo exigen.
- [Fuga o confusión del token de dev] → Tokens de vida corta en `.env.development.local` (ignorado, cargado solo en modo development), adjuntos bajo `import.meta.env.DEV`, sin logs ni commits; README los documenta como material local.
- [Las carreras reales de PostgreSQL no se reproducen en SQLite] → Los tests de concurrencia (publicación paralela y dos escrituras simultáneas del borrador) usan solicitudes paralelas y validan el mapeo determinista; el camino `FOR UPDATE` queda verificado contra el dialecto PostgreSQL en la fase 6.
- [Round-trip de migración aún no verificado en PostgreSQL/Supabase real] → Migración portable y verificada en SQLite limpio; verificación en PG explícita en la fase 6.
- [Índices únicos parciales y enums nativos entre dialectos] → SQLite y PostgreSQL soportan índices parciales; la migración reutiliza el patrón portable ya probado en la foundation.
- [El conmutador de rol demo puede confundirse con autorización] → El token determina la identidad; el rol renderizado proviene de `/me`; permisos verificados con tests 403 por rol.
- [Dependencias nuevas de formulario] → Instalación única de RHF+Zod tras validación Context7, sin librerías adicionales.

## Migration Plan

1. Alembic: nueva migración `brand_dna_versions` con enums e índices parciales; `upgrade` en base limpia y `downgrade` verificados.
2. Seeds idempotentes de marca y membresías demo ejecutables en cualquier entorno local.
3. Publicación transaccional cubierta por tests de transiciones inválidas antes de exponer la ruta al shell.
4. Rollback de la change: `alembic downgrade` del paso nuevo y retiro de rutas/seeds; sin datos de producción que migrar.
