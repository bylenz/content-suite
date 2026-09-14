## Context

Ver `proposal.md` y la spec `brand-knowledge`. Cambio anterior (005) dejó listo: puertos async `TextModel`/`EmbeddingModel`/`VisionModel`, `runner` con DI, fakes deterministas (incl. `FakeEmbeddingModel`), `Tracer` con `NoopTracer`/Langfuse, `errors.py` del módulo `ai` (`AIProviderNotConfiguredError`, etc.) y la invariante "SDKs solo en `ai/providers/`". El módulo `brand_dna` publica versiones inmutables con `knowledge_status` (`NOT_SYNCED`, `SYNCING`, `SYNCED`, `OUTDATED`, `FAILED`) y ya marca `SYNCED → OUTDATED` al editar borrador (`_mark_active_outdated`, intacto en esta change). Tests corren en SQLite in-memory con `Base.metadata.create_all`; producción es PostgreSQL (Supabase). `errors.py` centraliza el envelope y mapea 403/409 ya registrados.

WORKFLOWS.md fija la máquina de Knowledge: `NOT_SYNCED → SYNCING → SYNCED|FAILED`, `SYNCED → OUTDATED` (draft changes), `OUTDATED → SYNCING` **solo por publish changes**, `FAILED → SYNCING` (retry). `specs/04-creative-studio.md` exige Brand Knowledge disponible para generar/check/submit. Decisión de proveedor suministrada por el usuario: **los embeddings de producción usan un adapter OpenAI env-gated**.

## Goals / Non-Goals

**Goals:**

- Módulo `knowledge` con patrón espejo del existente (router -> service -> policies/repository), chunks versionados deterministas con IDs UUIDv5 estables y sync con claim atómico transaccional idempotente.
- Adapter OpenAI de embeddings env-gated, aislado en `app/ai/providers/`, con resolver desde settings y dependencia verificada (Context7) e instalada con `uv` en implementación.
- Retrieval híbrido interno reutilizable por Creative (spec 04) y Visual Audit (spec 05/06) con fail-safe explícito y sin degradaciones silenciosas.
- pgvector canónico en PostgreSQL sin nueva dependencia de vector; SQLite como seam de test honesto.
- Spans sanitizados vía el puerto `Tracer` existente con extensión aditiva mínima y tres operaciones distintas.

**Non-Goals:**

- No auto-sync al publicar (Brand DNA deja `NOT_SYNCED`; el Creator dispara el sync explícito, per spec 03).
- No expone el context builder por HTTP: es un servicio interno; su 503 lo mapeará el boundary de cada consumidor (Creative/Visual Audit).
- No implementa ANN index (hnsw/ivfflat): decenas de chunks por marca hacen scan exacto `<=>` suficiente; el índice se añade cuando el volumen lo justifique.
- No implementa brand assets ni upload ni storage ni signed URLs (spec 06); el contexto VISUAL de esta change es solo el textual `visual_rules` publicado. No UI nueva más allá del estado/acción de sync en superficies existentes.
- No cambia flujos de Brand DNA ni workflow states: `OUTDATED` se preserva tal como lo produce Brand DNA.

## Decisions

### Módulo `knowledge` y dependencias

`apps/api/app/knowledge` con `models.py`, `chunker.py`, `repository.py`, `service.py` (sync + context builder), `router.py`, `schemas.py`, `policies.py` y `errors.py`. Importa `app.ai.ports.EmbeddingModel`, `app.ai.errors.AIProviderNotConfiguredError`, `app.observability.ports` (Tracer/CapabilitySpan) y `app.brand_dna.models` (`BrandDnaVersion`, `KnowledgeStatus`, `BrandDnaStatus`) — sin ciclo: `brand_dna` no importa `knowledge`. Membership y autorización reutilizan `app.identity.repository.get_membership` + `authorize_brand_action` (patrón idéntico a `brand_dna.policies`). El SDK de OpenAI jamás se importa fuera de `app/ai/providers/`.

Alternativa descartada: colocar sync dentro de `brand_dna`. Violaba MODULES.md (Knowledge/RAG es módulo propio) y acoplaría embeddings a Brand DNA.

### Mapping canónico de chunking (fuente única; `chunker.py` y tests lo replican)

Un chunk por unidad atómica del documento; orden determinista por recorrido fijo de secciones. `metadata = {"order": int, "field": str, "index": int | None}`; `content` = texto atómico exacto; `rule_type` identifica el campo de origen.

| Sección / campo | rule_type | scope | mandatory |
|---|---|---|---|
| identity.purpose | purpose | TEXT | no |
| identity.positioning | positioning | TEXT | no |
| identity.personality_traits (join de labels) | personality_traits | TEXT | no |
| identity.audience | audience | TEXT | no |
| voice.usage_guide | usage_guide | TEXT | no |
| voice.tone_characteristics (join) | tone_characteristics | TEXT | no |
| voice.preferred_vocabulary (join) | preferred_vocabulary | TEXT | no |
| voice.avoid_vocabulary (join) | avoid_vocabulary | TEXT | **sí** |
| voice.do_examples (1 por item) | do_example | TEXT | no |
| voice.dont_examples (1 por item) | dont_example | TEXT | **sí** |
| communication.message_pillars (1 por pilar: `name: description`) | message_pillar | TEXT | no |
| communication.rules (1 por regla) | communication_rule | TEXT | **sí** |
| visual_rules.visual_personality | visual_personality | VISUAL | no |
| visual_rules.imagery_direction | imagery_direction | VISUAL | no |
| visual_rules.composition | composition | VISUAL | no |
| visual_rules.logo_usage | logo_usage | VISUAL | **sí** |
| restrictions.rules (1 por regla) | restriction | BOTH | **sí** |

Criterio de mandatory (AI_SYSTEM: always/never rules, hard restrictions, reglas visuales obligatorias): todo "never"/restricción dura y el uso de logo son mandatory; narrativas y guías quedan en el path semántico. Los joins de lista (`traits`, vocabularios) producen un único chunk por lista (mejor densidad semántica que un label aislado); las reglas/ejemplos/pilares sí se trocean por ítem.

Nota sobre el fail-safe "sin mandatory aplicables": un documento publicado válido siempre contiene mandatory para ambos scopes (`dont_examples`, `communication.rules` y `restrictions.rules` exigen `min_length=1` en el schema de Brand DNA; `logo_usage` es campo requerido), por lo que cero mandatory aplicables solo puede provenir de conocimiento incompleto/corrupto: el builder falla seguro en vez de construir contexto sin reglas duras.

### IDs deterministas UUIDv5 y fingerprint por versión

`chunk.id = uuid5(CHUNK_NAMESPACE, f"{brand_dna_version_id}|{order}|{field}|{index}")` con `CHUNK_NAMESPACE` un UUID fijo documentado en `chunker.py`. El documento de una versión publicada es inmutable y el recorrido es fijo, así que los IDs son estables a través de re-syncs y disjuntos entre versiones/campos. El delete+insert del reemplazo atómico reproduce el mismo conjunto de IDs.

`fingerprint = sha256` sobre la serialización canónica (ordenada) de la tupla completa de chunks `(id, section, rule_type, scope, mandatory, content, metadata)`. Se persiste por versión en cada sync exitoso; en el claim se compara para decidir idempotencia o regeneración. Al derivar del documento inmutable, un desajuste solo señala chunks corruptos/ajenos → regeneración.

Alternativa descartada: IDs autogenerados (uuid4). Cambiarían en cada re-sync e impedirían a los consumidores (spec 04: `applied_rule_ids uuid[]`) referenciar reglas de forma estable.

### Columna `metadata` reservada de SQLAlchemy

El atributo Python se llama `chunk_metadata` y se mapea explícitamente a la columna de base de datos `metadata` (`mapped_column("metadata", JSON)`), preservando el nombre canónico de `DATA_MODEL.md` sin chocar con el atributo reservado `metadata` de los modelos SQLAlchemy (Declarative API). El contrato HTTP expone el campo como `metadata`.

### Almacenamiento del embedding: dual dialecto, sin dependencia de vector

Columna `embedding` con dos representaciones según dialecto, resuelta en la migración y en el repository (nunca en el dominio):

- **PostgreSQL**: `CREATE EXTENSION IF NOT EXISTS vector` + columna `vector` **sin dimensión fija** (evita acoplar la dimensión al modelo de embedding; scan exacto `<=>` no requiere dimensión). Inserts/queries pasan el vector en formato texto (`'[0.1,0.2,...]'`) cast implícito — no se instala el paquete `pgvector` Python.
- **SQLite (dev/test)**: columna `JSON` con la lista de floats; el repository calcula coseno en Python. Es un seam de prueba documentado, no una simulación de producción: los tests saben que validan filtrado/aislamiento/orden del context builder, no el rendimiento de pgvector.

Ranking con orden total determinista en ambos dialectos: `ORDER BY distancia ASC, id ASC` (PG: `embedding <=> :q, id`; SQLite: sort Python con clave `(distancia, id)`), de modo que los empates exactos se resuelven siempre igual.

Alternativa descartada: `pgvector.sqlalchemy.Vector` — añade dependencia y exige dimensión fija; contradice el swap de provider del adapter. Alternativa descartada: JSON en ambos dialectos — perdería el camino canónico pgvector exigido por la spec.

### Estado de sync persistido: modelo, dimensión y fingerprint

Tres columnas aditivas nulables en `brand_dna_versions` (siguiendo el precedente de `knowledge_status`, que ya vive ahí): `knowledge_embedding_model text null`, `knowledge_embedding_dimensions int null`, `knowledge_fingerprint text null`. Se escriben solo en la finalización exitosa del sync, en la misma transacción que los chunks. El claim las compara contra los tres valores esperados, todos disponibles antes del claim y sin llamada al proveedor (modelo y dimensión declarados por el adapter desde su configuración; fingerprint computado del documento ACTIVE) para decidir idempotencia/regeneración; escribir el estado de Knowledge y su evidencia en la misma fila mantiene las transiciones atómicas (un solo row).

Alternativa descartada: tabla propia `brand_knowledge_sync` por versión. Añade una tabla y un join para los mismos datos que ya pertenecen al ciclo de vida de la versión.

### Adapter OpenAI de embeddings: env-gated, aislado y verificado

Decisión del usuario: producción usa OpenAI. Implementación:

- `app/ai/providers/openai_embeddings.py` con `OpenAIEmbeddingModel` que implementa el puerto `EmbeddingModel` (`name`, `dimensions`, `async def embed`). El SDK se importa **solo dentro de ese archivo**; las llamadas bloqueantes del SDK se envuelven con `asyncio.to_thread` (el dominio siempre espera corutinas, decisión 005).
- Extensión aditiva del puerto (mismo precedente que `CapabilitySpan`/`TraceSummary`): `EmbeddingModel` gana `dimensions: int`, declarado por cada adapter **desde su configuración y sin ninguna llamada al proveedor**. Es lo que hace que el modelo y la dimensión esperados estén disponibles antes del claim de sync y en la compatibilidad de retrieval, sin `await`. `FakeEmbeddingModel` (005) gana `dimensions = EMBEDDING_DIMENSIONS` y el doble de test 005 `FakeForTestEmbedding` (`tests/test_ai_ports.py`) gana igualmente el atributo `dimensions`: sin él, su asignación estática anotada al puerto falla `ty check` y su `isinstance` runtime falla (`runtime_checkable` exige presencia del atributo). La suite 005 sigue pasando con comportamiento intacto: la única edición en archivos 005 es que ambos dobles declaran el atributo; ningún test de comportamiento cambia.
- `app/ai/providers/__init__.py` expone `resolve_embedding_model(settings) -> EmbeddingModel | None`: devuelve el adapter solo si `ai_provider == "openai"` **y** `openai_api_key` está presente **y** la dimensión es cognoscible sin red: `openai_embedding_dimensions > 0` (se pasa también a la llamada del SDK; parámetro `dimensions` soportado en `text-embedding-3-*`, y en modelos de dimensión fija como `text-embedding-ada-002` solo se acepta la documentada) o el modelo está en la tabla documentada de defaults (`text-embedding-3-small` → 1536, `text-embedding-3-large` → 3072, `text-embedding-ada-002` → 1536). En cualquier otro caso (ausente o parcial, incluido modelo desconocido sin dimensión explícita) devuelve `None` con un único log sanitizado que nombra las variables faltantes, nunca sus valores (espejo de la resolución del tracer Langfuse). No se asume una dimensión fija global: la declara el adapter desde su configuración o el adapter no se construye.
- Settings nuevas (prefijo `CONTENT_SUITE_`, vacías/0 por defecto): `openai_api_key: str = ""`, `openai_embedding_model: str = ""` (vacía usa el default documentado del adapter, p. ej. `text-embedding-3-small`), `openai_embedding_dimensions: int = 0` (0 = dimensión por defecto documentada del modelo). `ai_provider` ya existe de 005.
- `None` es la única representación de proveedor no configurado (decisión 005): el service de sync lanza `AIProviderNotConfiguredError` → 503 solo en el boundary de esta change. Nunca un adapter "tonto" ni vectores falsos.
- La dependencia `openai` se verifica con Context7/documentación oficial (versión estable, Python 3.12, Pydantic v2) y se instala con `uv add` como tarea de implementación, documentando versión y hallazgos en la tarea; si la verificación invalida el enfoque, se registra el ajuste en la misma tarea.
- Tests del adapter con stub del SDK inyectado (sin red): batching, `name`/`dimensions` declarados sin red, errores del SDK → excepción explícita. La lógica de sync/retrieval se testa con `FakeEmbeddingModel` de 005.

Alternativa descartada: resolver el adapter dentro de `knowledge`. El resolver pertenece a `ai/providers/` (única capa que conoce proveedores); `knowledge` solo recibe `EmbeddingModel | None` por dependencia.

### Máquina de sync: validaciones primero, claim atómico, finalización separada

`POST sync` opera siempre sobre la versión ACTIVE de la marca:

1. Resolver membresía + rol `CREATOR` (403 antes de tocar recursos).
2. Resolver ACTIVE (read-only; sin ACTIVE → 404 envelope).
3. **Check de presencia del adapter antes de cualquier mutación**: `embedding_adapter is None` → 503 envelope (`AIProviderNotConfiguredError`) sin transición de estado.
4. **Chunking determinista y fingerprint antes del claim** (CPU puro sobre el documento inmutable de la ACTIVE ya resuelta; sin transacción abierta, sin `await`): el `chunker` produce el conjunto esperado de chunks con sus IDs y el fingerprint canónico; el modelo y la dimensión esperados son los declarados por el adapter (`name`/`dimensions`, resueltos de configuración sin llamar al proveedor). Con esto los tres valores del desajuste existen antes del claim y de cualquier `await`, y el claim no depende de ningún resultado posterior para decidir idempotencia.
5. **Claim condicional atómico** (transacción corta #1, commit inmediato, sin await dentro):
   `UPDATE brand_dna_versions SET knowledge_status = 'SYNCING' WHERE id = :vid AND status = 'ACTIVE' AND (knowledge_status IN ('NOT_SYNCED','FAILED') OR (knowledge_status = 'SYNCED' AND desajuste))` donde `desajuste` = `knowledge_embedding_model IS DISTINCT FROM :model OR knowledge_embedding_dimensions IS DISTINCT FROM :dimensions OR knowledge_fingerprint IS DISTINCT FROM :fingerprint`, con `:model`/`:dimensions`/`:fingerprint` = valores esperados computados en el paso 4. `rowcount == 1` → claim ganado; `rowcount == 0` → releer la fila en transacción fresca y responder: `SYNCED` sin desajuste (re-evaluado contra los mismos tres valores) → 200 idempotente (sin re-embed); `SYNCING` → 409 (sync concurrente); `OUTDATED` → 409 (publica los cambios del borrador). El UPDATE condicional es el punto de serialización: un segundo sync concurrente obtiene `rowcount = 0` inmediato, sin esperar ni bloquear.
6. `await embed(contents)` en batch único **sin transacción ni lock abiertos** → validación del lote (cardinalidad igual al conjunto de chunks, floats finitos, dimensión única e igual a la declarada por el adapter, norma > 0; violación → fallo).
7. **Finalización** (transacción #2): reemplazo atómico de los chunks de la versión (delete+insert con los UUIDv5 estables) + `SYNCED` + `knowledge_embedding_model/dimensions/fingerprint` (los valores esperados del paso 4, con la dimensión confirmada por el lote) → commit.
8. **Fallo** (transacción #3, solo si hubo claim): rollback de la finalización y `FAILED` persistido en transacción separada; los chunks previos sobreviven intactos; respuesta 503 envelope sanitizado.
9. Spans sanitizados `knowledge.sync` y `knowledge.embed` en éxito y error (ver trazabilidad).

`OUTDATED` solo lo produce el flujo existente de Brand DNA (edición de borrador) y solo "publish changes" lo saca de ahí (WORKFLOWS.md). El sync de una versión `OUTDATED` responde 409 sin tocar estado: la marca señala divergencia de borrador, no datos corruptos. La regeneración desde `SYNCED` por desajuste de modelo/dimensión/fingerprint es mantenimiento de datos derivados (chunks reemplazables, pgvector no es fuente de verdad), no un evento de workflow: el estado vuelve a `SYNCED` al finalizar.

Alternativa descartada: `SELECT ... FOR UPDATE` del brand mantenido a través del `await embed` (diseño previo). Sostiene un lock de fila durante la llamada al proveedor, acopla la duración de la transacción a latencia externa y en SQLite no aporta la garantía buscada. Alternativa descartada: `FOR UPDATE NOWAIT` en PostgreSQL — da 409 inmediato pero solo en PG y exige manejar el error de lock; el UPDATE condicional con `rowcount` es portable a ambos dialectos y basta.

Alternativa descartada: sync asíncrono con worker/cola. No existe razón medible (decenas de chunks, un batch de embeddings); la máquina sincrónica es auditable y testeable.

### Semántica OUTDATED para retrieval y consumidores

`build_context` sirve `SYNCED` y `OUTDATED`: los chunks de una versión `OUTDATED` corresponden exactamente a su documento ACTIVE publicado; la marca solo indica que existe un borrador con cambios no publicados (que jamás genera chunks ni filtra hacia consumidores). Reconciliación con specs/04 ("Brand Knowledge mandatory SYNCED para generar/check/submit" y WORKFLOWS "Brand Knowledge requerido disponible"): **disponible** = versión ACTIVE con estado servible (`SYNCED|OUTDATED`) y mandatory aplicables completos; el guard del consumidor se implementa contra esa disponibilidad (el fail-safe del builder), no contra la igualdad exacta con `SYNCED` — bloquear `OUTDATED` haría que cualquier edición de borrador paralice la generación contra el documento publicado vigente. `NOT_SYNCED`, `SYNCING` y `FAILED` no son servibles.

### Context builder: filtro antes de ranking, mandatory sin ranking

`build_context(session, *, brand_id, task: Literal["TEXT","VISUAL"], query: str, top_k, embedding_adapter, tracer)`:

1. Embedding adapter `None` → `KnowledgeNotAvailableError` (fail-safe, sin degradación a mandatory-only: el contexto parcial es exactamente el fallback silencioso prohibido).
2. Resolver versión ACTIVE (sin ACTIVE → `KnowledgeNotAvailableError`).
3. Estado servible (`SYNCED|OUTDATED`; otro estado → `KnowledgeNotAvailableError`).
4. Mandatory: todos los chunks `mandatory=true` cuyo scope interseca el de la tarea (`TEXT`∪`BOTH` o `VISUAL`∪`BOTH`). Si el conjunto es vacío → `KnowledgeNotAvailableError` (un documento válido siempre tiene mandatory; vacío = conocimiento incompleto).
5. **Compatibilidad de espacio vectorial antes de rankear**: `knowledge_embedding_model`/`knowledge_embedding_dimensions` persistidos MUST coincidir con los `name`/`dimensions` declarados por el adapter de consulta; NULL (evidencia ausente en un estado servible = corrupción) o desajuste → `KnowledgeNotAvailableError` sin rankear: los vectores persistidos pertenecen a otro espacio y la versión necesita re-sync con el adapter activo.
6. Semántico: `await embed([query])` con los fallos del adapter capturados y convertidos a `KnowledgeNotAvailableError` (nunca se rankea con el espacio parcialmente desconocido); validación del único vector de consulta (cardinalidad exactamente 1, floats finitos, norma > 0, dimensión igual a la persistida; violación → `KnowledgeNotAvailableError`); ranking de los chunks no-mandatory del scope, filtrados por `brand_id` + `brand_dna_version_id` **antes** de ordenar; top-k con `k` acotado 1–20 (default 8), orden total `(distancia, id)`.
7. Span `knowledge.retrieve` (conteos). Devuelve `BuiltContext` (dataclass interno, sin endpoint): `brand_dna_version_id`, `mandatory: list[KnowledgeRule]`, `semantic: list[KnowledgeRule]`, con `KnowledgeRule = (id, section, rule_type, scope, content)` — los IDs permiten a spec 04 persistir `applied_rule_ids`.

`KnowledgeNotAvailableError` queda sin handler HTTP en esta change: la lanzan consumidores internos; su 503 lo registra el boundary de Creative (spec 04), decisión ya asentada en API.md.

Alternativa descartada: SQL único con ranking y mandatory juntos. Difuminaría la invariante "mandatory no depende de similarity" y complicaría el testeo del fail-safe.

### Endpoints y contratos

- `GET /brands/{brand_id}/brand-knowledge` → `{brand_dna_version: {id, version, knowledge_status}, chunks: [{id, section, rule_type, scope, mandatory, content, metadata, created_at}]}` (sin embeddings). Lectura: cualquier rol con membresía. Chunks solo de la ACTIVE; un borrador jamás genera chunks, así que no hay fuga posible de draft.
- `GET .../brand-knowledge/status` → `{brand_dna_version_id, version, knowledge_status, chunk_count, embedding_model}` (`chunk_count`/`embedding_model` null si no hay sync exitoso). Mismos permisos de lectura.
- `POST .../sync` (sin body) → recurso de estado + `chunk_count`; 403/404/409/503 por envelope. Idempotente por diseño para el mismo modelo/fingerprint (retry tras respuesta = mismo resultado observable), sin idempotency key.
- Orden **membership-first**: policies resuelven membresía/rol antes de cualquier lookup de marca o versión — un no-miembro recibe 403 aunque la marca no exista. Con membresía y sin ACTIVE: 404 envelope en los tres endpoints.
- Handlers nuevos en `errors.py`: `SyncConflictError → 409` (reuso de código `INVALID_WORKFLOW_TRANSITION`, detalles distinguibles: "sync en curso" vs "OUTDATED: publica los cambios del borrador") y `AIProviderNotConfiguredError → 503 SERVICE_UNAVAILABLE` (mensaje sanitizado, sin secretos). `PermissionDeniedError`/404 ya cubiertos.

Sin paginación: decenas de chunks por marca (YAGNI, documentado).

### Trazabilidad: extensión aditiva del contrato 005, tres operaciones

Cambios aditivos (la suite 005 pasa sin modificaciones):

- `CapabilitySpan` gana `operation: str | None = None` y `prompt_version` pasa a `str | None = None` (el runner de 005 sigue pasándolo siempre; las operaciones Knowledge van sin prompt y con `operation`). Invariante de nombre: la construcción del span valida que al menos uno de `operation`/`prompt_version` esté presente (ambos ausentes → error de construcción, nunca un span anónimo silencioso).
- `TraceSummary` amplía su allowlist: `contract: Literal[..., "KnowledgeSync", "KnowledgeEmbed", "KnowledgeRetrieval"]`; `check_count`/`finding_count` reciben default `0` (conservan cotas 0–100); nuevos campos escalares opcionales `chunk_count`/`mandatory_count`/`semantic_count` (0–10000, default None). Validadores: `content_type` solo para `CreativeOutput` (regla existente); los conteos Knowledge solo para contratos `Knowledge*`; contratos `Knowledge*` dejan `check_count`/`finding_count` en su default `0`. `extra="forbid"` se conserva: sigue sin haber texto libre, por diseño.
- El adapter Langfuse nombra cada observación con `span.operation or span.prompt_version` (hoy usa `span.prompt_version`, de modo que los nombres de los spans con prompt de 005 se conservan exactamente) e incorpora `operation` al metadata del span cuando existe. `NoopTracer` no cambia.

Tres operaciones distintas (no dos ambiguas):

| operation | cuándo | summary |
|---|---|---|
| `knowledge.sync` | sync completo de la versión (éxito/error) | `KnowledgeSync`, `chunk_count`, `ok` |
| `knowledge.embed` | llamada al adapter dentro del sync | `KnowledgeEmbed`, `chunk_count` = tamaño del lote, `ok` |
| `knowledge.retrieve` | construcción de contexto | `KnowledgeRetrieval`, `mandatory_count`/`semantic_count`, `ok` |

Entidad `brand_knowledge:{version_id}`, `model` = nombre del embedding adapter, error sanitizado = `type(exc).__name__`. El guard de emisión se replica (fallo del tracer jamás rompe sync ni retrieval).

Alternativa descartada: abusar `prompt_version` como etiqueta de operación. Falsearía la semántica del campo y acoplaría Knowledge al registry de prompts. Alternativa descartada: un único span de sync con la llamada al adapter embebida. Fusiona dos operaciones con latencias y modos de fallo distintos y oculta el costo del embedding.

### Frontend: estado real + acción de sync, sin pantallas nuevas

`KNOWLEDGE_STATUS_VIEW` y las copys de Brand DNA/Dashboard pasan a reflejar los cinco estados reales (`SYNCING` y `FAILED` incluidos) sin prometer sincronización automática; `OUTDATED` se explica como "borrador con cambios pendientes de publicar" (la acción de sync está deshabilitada con ese motivo). En la página de Brand DNA, el CREATOR (rol ya resuelto en sesión) ve un botón "Sincronizar Knowledge" sobre la versión ACTIVE que llama a `POST /brands/{id}/brand-knowledge/sync` con TanStack Query (mutación + invalidación de queries de DNA/status); 503/409/404 se muestran con los mensajes del envelope (estado de error inline, sin toast global nuevo). Reviewers ven solo el estado. No se habilita nada de Creative.

Alternativa descartada: pantalla nueva de Knowledge. La spec pide superficies existentes; la lista de chunks no aporta al flujo actual.

### Sin assets físicos en el contexto VISUAL

El contexto `VISUAL` de 006 proviene exclusivamente de las secciones textuales `visual_rules` del documento publicado. No se embeben imágenes, no se referencian `brand_assets`, no se añade storage: upload, storage privado, signed URLs y cualquier RAG visual sobre assets pertenecen a la capability de Visual Compliance (spec 06). Esta change no afirma ni habilita asset visual RAG.

## Risks / Trade-offs

- [pgvector solo verificable manualmente] → migración y camino `<=>` quedan documentados como verificación manual en PostgreSQL (tarea final); SQLite cubre la lógica de dominio.
- [Dimensión del vector sin ANN index] → scan exacto suficiente en MVP; si el volumen crece, migración futura fija dimensión + hnsw (documento el upgrade path).
- [SQLite ranking en Python puede divergir de pgvector] → los tests no afirman equivalencia numérica; validan filtro, aislamiento, orden determinista (empate por `id`) y fail-safe.
- [Sync síncrono bloquea el request] → un batch de embeddings por sync es rápido; si un proveedor real tarda, se documenta como deuda medible antes de introducir colas.
- [Reemplazo delete+insert puede ser costoso con muchos chunks] → decenas de filas por versión; irrelevante en MVP.
- [SDK OpenAI cambia API] → verificación previa obligatoria (Context7/official) y adapter aislado en `ai/providers/`; tests con stub, sin red.
- [Regeneración desde SYNCED por desajuste] → decisión explícita de mantenimiento de datos derivados (chunks reemplazables); documentada aquí y testeada.

## Migration Plan

1. Additive: migración Alembic `brand_knowledge_chunks` (PK UUIDv5, FK versión, índices brand/versión, mandatory parcial, scope) + columnas nulables `knowledge_embedding_model/dimensions/fingerprint` en `brand_dna_versions`, con branch por dialecto (`vector` en PostgreSQL, JSON en SQLite); registro en `alembic/env.py`; módulo `knowledge` completo + adapter/resolver OpenAI + handlers nuevos; ajuste frontend de estado/sync. `uv add openai` tras verificación documentada.
2. Verificación: `uv run ruff check`, `uv run ty check`, `uv run pytest` (SQLite), `alembic upgrade head` + `downgrade` round-trip en SQLite, frontend `lint`/`typecheck`/`build`, auditoría de imports (OpenAI solo en `ai/providers/`; `langfuse` solo en su adapter), `openspec validate --strict`; verificación manual de PostgreSQL/pgvector documentada (no ejecutada en CI).
3. Rollback: revert de la migración + eliminación del módulo `knowledge`, handlers y ajustes frontend (`uv remove openai` si se desea); no hay datos ni contratos previos que revertir (chunks son derivados regenerables).
