## Purpose

Convierte Brand DNA publicado en Brand Knowledge recuperable: chunks versionados deterministas con IDs estables, sync explícito con claim atómico y estados reales, embeddings generados solo vía adapter env-gated (OpenAI) aislado en `ai/providers`, retrieval híbrido (mandatory + semántico) estrictamente aislado por marca y versión, y endpoints con RBAC que bloquean a los consumidores cuando falta contexto obligatorio.

## ADDED Requirements

### Requirement: Chunking determinista y versionado con IDs estables
El sistema SHALL derivar chunks de Knowledge de forma determinista a partir del documento de una versión Brand DNA publicada (ACTIVE), según un mapping canónico que asigna a cada unidad atómica su sección, tipo de regla, scope (`TEXT`, `VISUAL`, `BOTH`) y flag `mandatory`. Cada chunk SHALL recibir un `id` UUIDv5 determinista derivado de la versión publicada y del campo/índice canónicos: re-sincronizar la misma versión reproduce exactamente los mismos IDs y dos versiones o unidades canónicas distintas nunca colisionan. El sistema SHALL calcular por versión un fingerprint estable del conjunto canónico de chunks (hash sobre la secuencia ordenada de chunks). Los chunks pertenecen exactamente a la versión que los originó: publicar una nueva versión o editar un borrador MUST NOT modificar ni sobrescribir los chunks de versiones ya publicadas. pgvector no es fuente de verdad: el documento Brand DNA publicado es canónico y los chunks son derivados reemplazables por versión.

#### Scenario: Re-sync de la misma versión
- **WHEN** se sincroniza dos veces la misma versión ACTIVE sin cambios en su documento y con el mismo embedding adapter
- **THEN** el conjunto de chunks resultante es idéntico: mismos IDs UUIDv5, contenido, orden y metadata deterministas

#### Scenario: Publicación de una nueva versión
- **WHEN** se publica una nueva versión de Brand DNA y se sincroniza
- **THEN** los chunks de la versión anterior permanecen intactos y la nueva versión obtiene su propio conjunto con IDs propios

#### Scenario: IDs estables y únicos
- **WHEN** se comparan los IDs de los chunks de una versión tras un re-sync y los de cualquier otra versión de la misma marca
- **THEN** los IDs de la versión son idénticos entre syncs y disjuntos de los de cualquier otra versión

### Requirement: Sync explícito con claim atómico, estados y retry idempotente
El sistema SHALL sincronizar Knowledge solo desde la versión ACTIVE y solo a petición explícita de un Creator. El orden de validación SHALL ser: membresía/rol (403), existencia de versión ACTIVE (404), presencia del embedding adapter y computación determinista del conjunto de chunks y su fingerprint sobre el documento de la versión ACTIVE; el check de adapter MUST ocurrir antes de cualquier mutación de estado, y el chunking y el fingerprint MUST completarse antes del claim, sin transacción abierta ni `await`. La transición a `SYNCING` SHALL ejecutarse como claim condicional atómico (UPDATE condicional sobre `knowledge_status`) en una transacción corta comprometida antes de cualquier `await`: ninguna transacción ni lock de base de datos SHALL mantenerse abierto a través de la llamada al proveedor de embeddings. Estados fuente válidos del claim: `NOT_SYNCED`, `FAILED` (retry) y `SYNCED` con desajuste persistido de modelo de embedding, dimensión o fingerprint (regeneración de datos derivados, no evento de workflow); los tres valores esperados del desajuste MUST estar disponibles antes del claim y sin llamar al proveedor: modelo y dimensión declarados por el adapter desde su configuración y fingerprint computado del documento ACTIVE. Sincronizar una versión `SYNCED` sin desajuste SHALL devolver el estado vigente sin re-embedding ni duplicación (retry idempotente). Un sync cuyo adapter falla o devuelve un lote inválido deja estado `FAILED` con los chunks previos intactos, permite retry y responde 503 controlado. Un sync concurrente sobre una versión `SYNCING` MUST responder 409 inmediato (sin esperar el primer sync). Un sync sobre una versión `OUTDATED` MUST responder 409 sin transición de estado ni re-embedding: `OUTDATED` solo sale de su estado cuando se publican los cambios del borrador (regla de Brand DNA ya acordada) y sincronizar la versión ACTIVE sin cambios MUST NOT limpiar la marca.

#### Scenario: Sync exitoso
- **WHEN** un Creator sincroniza una versión ACTIVE con embedding adapter disponible
- **THEN** el estado pasa a `SYNCED`, los chunks quedan persistidos con sus IDs estables, se persisten modelo/dimensión/fingerprint del sync y la respuesta incluye el conteo de chunks

#### Scenario: Fallo de embedding
- **WHEN** el adapter de embeddings falla o devuelve un lote inválido durante el sync
- **THEN** el estado queda `FAILED`, no se persisten chunks parciales, la respuesta es 503 con envelope y un retry posterior puede llevarlo a `SYNCED`

#### Scenario: Retry idempotente
- **WHEN** un Creator repite el sync de una versión `SYNCED` sin desajuste de modelo/dimensión/fingerprint
- **THEN** la operación responde con el estado vigente sin volver a embeber ni duplicar chunks

#### Scenario: Regeneración por cambio de modelo
- **WHEN** se sincroniza una versión `SYNCED` cuyo modelo de embedding persistido difiere del adapter activo
- **THEN** el sync regenera los vectores (claim desde `SYNCED` válido por desajuste) y persiste el nuevo modelo/dimensión

#### Scenario: Regeneración por cambio de dimensión
- **WHEN** se sincroniza una versión `SYNCED` cuya dimensión persistida difiere de la declarada por el adapter activo
- **THEN** el claim procede por desajuste y el sync regenera los vectores persistiendo la nueva dimensión

#### Scenario: Sync concurrente
- **WHEN** dos syncs llegan simultáneamente sobre la misma versión
- **THEN** exactamente uno gana el claim atómico y completa; el otro responde 409 inmediato con el envelope existente y no corrompe el estado ni duplica chunks

#### Scenario: Sync sobre OUTDATED
- **WHEN** se intenta sincronizar la versión ACTIVE de una marca cuyo `knowledge_status` es `OUTDATED`
- **THEN** la respuesta es 409 con envelope que indica publicar los cambios del borrador, y el estado permanece `OUTDATED`

#### Scenario: Proveedor de embeddings no configurado
- **WHEN** un Creator intenta sincronizar sin embedding adapter configurado
- **THEN** la respuesta es 503 con envelope, el `knowledge_status` permanece inalterado (sin `SYNCING` ni `FAILED`) y no se generan chunks con vectores falsos

### Requirement: Embeddings solo vía adapter env-gated aislado en `ai/providers`
Los embeddings SHALL generarse exclusivamente a través del puerto `EmbeddingModel` inyectado (AI Platform, change 005); el sync y el retrieval MUST NOT importar SDKs de proveedor directamente ni inventar vectores. El proveedor de producción es OpenAI: su adapter SHALL implementarse únicamente bajo `app/ai/providers/`, con el SDK importado solo dentro del archivo del adapter, y SHALL ser asíncrono (el SDK bloqueante se envuelve, p. ej. `asyncio.to_thread`). El puerto `EmbeddingModel` SHALL exponer `name` y `dimensions` como atributos declarados por el adapter desde su propia configuración, sin ninguna llamada al proveedor; una configuración que no permita conocer el modelo o la dimensión SHALL tratarse como parcial. Un resolver SHALL construir el adapter desde settings solo con configuración completa (`CONTENT_SUITE_AI_PROVIDER=openai` y API key presente); configuración ausente o parcial resuelve a adapter `None` con un único log sanitizado que nombra las variables faltantes, nunca sus valores. Con adapter `None`, el sync responde 503 controlado (error existente `AIProviderNotConfiguredError` de 005; el 503 se registra solo en el boundary de API de esta change). La dependencia del SDK MUST verificarse con Context7/documentación oficial e instalarse con `uv` como tarea de implementación, antes de usarla. Los tests del adapter usan un stub del SDK sin red; la lógica de sync/retrieval se testa con el fake determinista de 005.

#### Scenario: Adapter activo por entorno
- **WHEN** las variables de proveedor están completas al construir la dependencia
- **THEN** el resolver devuelve el adapter OpenAI y el sync puede completar `SYNCED` con embeddings reales

#### Scenario: Configuración parcial del proveedor
- **WHEN** falta alguna variable de proveedor requerida
- **THEN** el resolver devuelve `None` con un único log que nombra la variable faltante sin exponer valores, y el sync responde 503 sin transición de estado

#### Scenario: Dimensión declarada sin llamada al proveedor
- **WHEN** se construye el adapter con configuración completa
- **THEN** `name` y `dimensions` quedan resueltos desde la configuración del adapter sin ninguna llamada al proveedor, y están disponibles para el claim de sync y la compatibilidad de retrieval

#### Scenario: Aislamiento del SDK
- **WHEN** se auditan estáticamente los imports de `apps/api/app`
- **THEN** el SDK de OpenAI solo aparece en `ai/providers/` y ningún router o service de dominio lo importa

### Requirement: Integridad del vector store y ranking determinista
Cada versión sincronizada con éxito SHALL persistir junto a su estado el modelo de embedding usado, la dimensión de los vectores y el fingerprint canónico del conjunto de chunks. El sync MUST validar el lote devuelto por el adapter antes de persistir: misma cardinalidad que los chunks, floats finitos (sin NaN/Inf), una única dimensión igual en todo el lote y vectores no nulos (norma > 0); cualquier violación falla el sync a `FAILED` sin persistir chunks parciales. El ranking semántico SHALL ser un orden total determinista en ambos dialectos: distancia ASC y, ante empate exacto, `id` de chunk ASC. Un desajuste persistido de modelo, dimensión o fingerprint respecto a los valores esperados (modelo y dimensión declarados por el adapter activo, fingerprint computado del documento ACTIVE) MUST tratarse como desajuste en el claim y provocar regeneración en el siguiente sync; la evaluación ocurre antes del claim y sin llamada al proveedor.

#### Scenario: Lote inválido
- **WHEN** el adapter devuelve vectores con dimensiones mezcladas, valores no finitos o un vector nulo
- **THEN** el sync falla a `FAILED` sin persistir nada y el error queda registrado de forma sanitizada

#### Scenario: Empate exacto en similarity
- **WHEN** dos chunks del mismo scope empatan en distancia exacta con la consulta
- **THEN** el orden de ranking queda definido por el `id` de chunk ASC, de forma estable y reproducible

### Requirement: Retrieval híbrido filtrado y fail-safe
El context builder SHALL construir contexto por tarea (`TEXT` o `VISUAL`) combinando: todas las reglas mandatory aplicables al scope de la tarea (siempre presentes, sin depender de similarity) y top-k semántico. La búsqueda semántica MUST filtrar por `brand_id` y `brand_dna_version_id` antes de cualquier ranking, y SHALL segmentar por scope (`TEXT` usa `TEXT`+`BOTH`; `VISUAL` usa `VISUAL`+`BOTH`). El builder MUST fallar con error explícito de Knowledge no disponible, sin contexto parcial, cuando: no existe versión ACTIVE; su `knowledge_status` no es servible (`NOT_SYNCED`, `SYNCING`, `FAILED`); la versión servable no tiene ningún chunk mandatory aplicable al scope de la tarea; el embedding adapter de la consulta es `None` (sin degradación silenciosa a mandatory-only); el modelo o la dimensión persistidos de la versión son NULL o difieren de los declarados por el adapter de consulta (espacio vectorial incompatible: la versión necesita re-sync y jamás se rankean espacios mezclados); o el adapter de consulta falla o devuelve un vector de consulta inválido (cardinalidad distinta de 1, valores no finitos, norma 0 o dimensión distinta de la persistida). Son servibles `SYNCED` y `OUTDATED`: los chunks de una versión `OUTDATED` corresponden exactamente a su documento ACTIVE publicado y la marca solo señala divergencia de borrador. El resultado (`BuiltContext`) SHALL exponer los IDs de los chunks mandatory y semánticos para que los consumidores persistan las reglas aplicadas. En PostgreSQL la búsqueda vectorial usa pgvector (`<=>`); en SQLite (dev/test) se usa un ranking determinista documentado como seam de prueba que no finge búsqueda vectorial productiva.

#### Scenario: Mandatory siempre presente
- **WHEN** se construye contexto para una tarea con Knowledge sincronizado
- **THEN** la respuesta incluye todas las reglas mandatory del scope de la tarea aunque ninguna sea semánticamente similar a la consulta

#### Scenario: Aislamiento por marca y versión
- **WHEN** dos marcas o dos versiones distintas tienen Knowledge sincronizado
- **THEN** el retrieval de una marca/versión nunca devuelve chunks de la otra, ni siquiera parcialmente en el top-k

#### Scenario: Knowledge obligatorio ausente
- **WHEN** se solicita contexto sin versión ACTIVE, sin sync exitoso, o en estado `NOT_SYNCED`/`SYNCING`/`FAILED`
- **THEN** el builder falla con error explícito de Knowledge no disponible, sin devolver contexto parcial

#### Scenario: Sin chunks mandatory aplicables
- **WHEN** una versión servable no contiene ningún chunk mandatory aplicable al scope de la tarea solicitada
- **THEN** el builder falla con error explícito de Knowledge no disponible en lugar de construir contexto solo semántico

#### Scenario: Adapter de consulta ausente
- **WHEN** se construye contexto con embedding adapter `None`
- **THEN** el builder falla con error explícito de Knowledge no disponible, sin degradar a mandatory-only ni a contexto parcial

#### Scenario: Espacio vectorial incompatible
- **WHEN** se construye contexto de una versión sincronizada cuyo modelo o dimensión persistidos difieren de los declarados por el adapter de consulta activo
- **THEN** el builder falla con error explícito de Knowledge no disponible antes de rankear, sin contexto parcial ni distancias entre espacios distintos

#### Scenario: Vector de consulta malformado
- **WHEN** el adapter de consulta falla o devuelve cero vectores, más de uno, valores no finitos, norma 0 o una dimensión distinta de la persistida
- **THEN** el builder falla con error explícito de Knowledge no disponible en lugar de rankear con un vector inválido

#### Scenario: OUTDATED servible
- **WHEN** se construye contexto de una versión `OUTDATED`
- **THEN** el builder devuelve los chunks de esa versión (el documento ACTIVE publicado) con sus mandatory completos

#### Scenario: Segmentation por tarea
- **WHEN** se construye contexto para una tarea `VISUAL` y otra `TEXT` sobre la misma versión
- **THEN** cada resultado solo incluye chunks de los scopes aplicables a su tarea, además de los mandatory compartidos (`BOTH`)

### Requirement: Endpoints de Knowledge con RBAC backend y orden membership-first
El sistema SHALL exponer `GET /api/v1/brands/{brand_id}/brand-knowledge`, `GET .../brand-knowledge/status` y `POST .../brand-knowledge/sync`. Toda comprobación de acceso SHALL resolver primero membresía y rol (403 antes de evaluar cualquier recurso de la marca, incluida la existencia de la marca o su versión). Lectura (chunks publicados de la versión ACTIVE y estado) requiere membresía con cualquier rol; el sync requiere rol `CREATOR`. Con membresía válida y sin versión ACTIVE, los tres endpoints responden 404 con envelope. Los chunks solo existen para versiones publicadas: el sistema MUST NOT exponer información derivada de borradores a ningún rol. Los errores se normalizan con el envelope existente: 403 sin membresía o rol insuficiente, 404 sin versión ACTIVE, 409 sync concurrente o versión `OUTDATED` (detalles distinguibles), y 503 proveedor ausente o fallo de embedding.

#### Scenario: Reviewer lee Knowledge publicado
- **WHEN** un Content Reviewer o Visual Reviewer consulta los endpoints de lectura
- **THEN** recibe el estado y los chunks (con sus IDs) de la versión ACTIVE sincronizada, sin información de borradores

#### Scenario: Reviewer no puede sincronizar
- **WHEN** un rol distinto de `CREATOR` llama a `POST .../sync`
- **THEN** la respuesta es 403 con envelope y el estado no cambia

#### Scenario: Usuario sin membresía
- **WHEN** un usuario autenticado sin membresía consulta cualquier endpoint de Knowledge, exista o no la marca
- **THEN** la respuesta es 403 antes de resolver cualquier recurso de la marca

#### Scenario: Lectura sin versión ACTIVE
- **WHEN** un miembro consulta chunks o status de una marca sin versión ACTIVE
- **THEN** la respuesta es 404 con envelope

### Requirement: Trazabilidad sanitizada de sync, embedding y retrieval
El sistema SHALL emitir spans sanitizados a través del puerto `Tracer` (change 005) como tres operaciones distintas e inequívocas: `knowledge.sync` (sync completo de la versión, con conteo de chunks persistidos), `knowledge.embed` (llamada al adapter de embeddings dentro del sync, con el tamaño del lote) y `knowledge.retrieve` (construcción de contexto, con conteos mandatory/semánticos). La extensión del contrato 005 SHALL ser aditiva: `CapabilitySpan` gana `operation` y permite `prompt_version` ausente (None) para operaciones sin prompt; `TraceSummary` amplía su allowlist con los contratos Knowledge y conteos escalares acotados, conservando `extra="forbid"`; la suite de tests de 005 MUST seguir pasando sin cambios. Un span SHALL llevar al menos un identificador de nombre: `operation` o `prompt_version` (ambos ausentes es inválido en construcción); el adapter Langfuse SHALL nombrar cada observación con `operation` cuando existe y con `prompt_version` en caso contrario, preservando los nombres de los spans con prompt de 005. Los spans MUST NOT contener prompts, respuestas crudas, contenidos de chunks, embeddings ni secretos; el error sanitizado se limita al nombre de la clase de excepción. Los fallos del tracer se degradan sin romper la operación de dominio, y el tracer no cambia estados de workflow ni persiste entidades.

#### Scenario: Spans separados por operación
- **WHEN** un sync completa seguido de un retrieval
- **THEN** se emiten spans distintos `knowledge.sync`, `knowledge.embed` y `knowledge.retrieve`, cada uno con entidad (versión), modelo, latencia y conteos acotados, sin payloads crudos

#### Scenario: Fallo del tracer
- **WHEN** el tracer falla durante un sync o retrieval
- **THEN** la operación de dominio completa normalmente y el fallo queda registrado de forma sanitizada

#### Scenario: Nombre de observación según tipo de span
- **WHEN** se emiten spans de capabilities con prompt (005) y spans Knowledge con `operation` y sin `prompt_version`
- **THEN** el nombre de cada observación es el `prompt_version` para los primeros y el `operation` para los segundos, y ningún span se construye con ambos ausentes

### Requirement: Contexto VISUAL estrictamente textual del Brand DNA publicado
El contexto VISUAL de esta capability SHALL construirse únicamente a partir de las secciones textuales `visual_rules` del Brand DNA publicado. El sistema MUST NOT ingerir, almacenar, embeber ni recuperar assets físicos de marca en esta change: upload, storage privado, signed URLs y cualquier ampliación del contexto visual sobre assets pertenecen a la capability de Visual Compliance (spec 06).

#### Scenario: Contexto visual sin assets
- **WHEN** se construye contexto para una tarea `VISUAL`
- **THEN** el resultado proviene solo de las secciones textuales `visual_rules` publicadas y no referencia ni requiere assets físicos
