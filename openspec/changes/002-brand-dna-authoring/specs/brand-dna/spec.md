## Purpose

Permite crear, editar y publicar el documento Brand DNA de una marca como fuente de verdad estructurada y versionada, con contratos de lectura por rol, autorización resuelta en backend, publicación transaccional concurrente e idempotente, envelope de error centralizado y semántica de estado de Knowledge según `WORKFLOWS.md`, sin implementar la sincronización de Brand Knowledge.

## ADDED Requirements

### Requirement: Documento Brand DNA canónico
El documento Brand DNA SHALL cumplir exactamente el contrato canónico estricto de cinco secciones operativas definido en `design.md`: identidad (propósito, posicionamiento, rasgos de personalidad y audiencia), voz (características del tono, guía de uso, vocabulario preferido y evitado, ejemplos de hacer y no hacer), comunicación (pilares de mensaje y reglas), reglas visuales (personalidad visual, dirección de imagen, composición y uso de logo) y restricciones (reglas prohibitivas). Cada campo SHALL ajustarse al tipo, cardinalidad y límites del contrato. La API SHALL normalizar espacios (recorte de extremos de todo string) antes de validar y persistir, SHALL rechazar secciones, campos o claves desconocidas y SHALL rechazar con un error de validación cualquier documento que incumpla el contrato, sin crear ni modificar versión alguna.

#### Scenario: Documento válido
- **WHEN** un Creator guarda un borrador cuyo documento contiene las cinco secciones con sus campos obligatorios completos y dentro de los límites
- **THEN** la API acepta el documento y lo persiste como parte de la versión en borrador

#### Scenario: Documento inválido
- **WHEN** un Creator guarda un borrador cuyo documento omite una sección obligatoria o envía campos con tipos o cardinalidades inválidas
- **THEN** la API responde con un error de validación con las rutas de campo ofensivas y no crea ni modifica ninguna versión

#### Scenario: Campos desconocidos rechazados
- **WHEN** el documento incluye una sección, campo o clave no definida en el contrato canónico
- **THEN** la API responde con un error de validación que identifica la ruta desconocida y no persiste cambio alguno

#### Scenario: Normalización de espacios
- **WHEN** un campo textual llega con espacios en los extremos
- **THEN** la API lo persiste recortado, y si el string queda vacío tras el recorte responde con un error de validación

### Requirement: Autorización de escritura exclusiva del Creator
Las operaciones de creación, edición y publicación de Brand DNA SHALL estar permitidas únicamente a miembros con rol `CREATOR` de la marca, resueltas siempre en el backend a partir de la membresía persistida. Un usuario sin membresía o con rol de revisor SHALL recibir un error de permiso sin modificar ningún estado.

#### Scenario: Creator edita su marca
- **WHEN** un usuario autenticado con membresía `CREATOR` en la marca edita el borrador o publica
- **THEN** la API autoriza la operación

#### Scenario: Revisor intenta escribir
- **WHEN** un usuario con rol `CONTENT_REVIEWER` o `VISUAL_REVIEWER` intenta crear, editar o publicar Brand DNA
- **THEN** la API responde con error de permiso y no cambia ningún dato

#### Scenario: Usuario sin membresía
- **WHEN** un usuario autenticado sin membresía en la marca intenta cualquier operación de Brand DNA
- **THEN** la API responde con error de permiso

#### Scenario: Identidad ausente o inválida
- **WHEN** una solicitud sin identidad válida llega a cualquier endpoint de Brand DNA
- **THEN** la API responde con error de autenticación

### Requirement: Contratos de lectura por rol
Los endpoints de lectura SHALL filtrar sus respuestas según el rol resuelto en backend. Los revisores (`CONTENT_REVIEWER`, `VISUAL_REVIEWER`) SHALL acceder únicamente a versiones `ACTIVE` y `ARCHIVED` —metadatos, conteos y documento— y NINGUNA respuesta hacia un revisor SHALL incluir un recurso de versión `DRAFT` ni su id, número de versión, conteos, metadatos o documento. El `knowledge_status = OUTDATED` de la versión `ACTIVE` MAY comunicar de forma genérica que existen cambios pendientes de publicación; ese estado pertenece a la propia versión activa y no prueba, nombra ni identifica un borrador. El `CREATOR` SHALL además leer su `DRAFT` completo. `GET /api/v1/brands/{brand_id}/brand-dna` SHALL responder `{active, draft}` donde `draft` es el recurso completo del borrador para el `CREATOR` y `null` para revisores o cuando no existe borrador; `GET .../brand-dna/versions` SHALL excluir toda entrada `DRAFT` para revisores; `GET .../brand-dna/versions/{version}` SHALL entregar el recurso completo de una versión publicada a cualquier miembro y SHALL responder 404 a un revisor que solicite una versión en `DRAFT`.

#### Scenario: Miembro lee el DNA vigente
- **WHEN** cualquier miembro de la marca consulta el Brand DNA vigente
- **THEN** recibe la versión `ACTIVE` con su documento, número de versión, fechas y estado de Knowledge

#### Scenario: Revisor sin acceso a borrador
- **WHEN** un revisor consulta el DNA vigente, el historial o el detalle de una versión existiendo un `DRAFT`
- **THEN** `draft` llega `null`, la lista no contiene entrada alguna del borrador y la solicitud directa de la versión en `DRAFT` responde 404, sin exponer id, número, conteos ni documento del borrador

#### Scenario: Creator consulta con su borrador en curso
- **WHEN** un `CREATOR` consulta la marca teniendo versión `ACTIVE` y un `DRAFT` en curso
- **THEN** recibe la versión `ACTIVE` vigente junto con el recurso completo del borrador, incluido su documento

#### Scenario: Marca sin versión publicada
- **WHEN** un miembro consulta una marca que no tiene versión publicada
- **THEN** la respuesta indica con `active` en `null` que no existe DNA publicado y no expone el borrador a revisores

### Requirement: Borrador único y editable por marca
Cada marca SHALL tener como máximo una versión en estado `DRAFT` a la vez. La edición SHALL aplicar solo sobre el borrador: si no existe borrador, la edición SHALL crear la siguiente versión como `DRAFT` inicializada a partir del documento de la versión `ACTIVE` vigente cuando exista. Las versiones `ACTIVE` y `ARCHIVED` SHALL ser inmutables y nunca modificarse. Toda mutación del borrador —cálculo de versión, creación o actualización— SHALL ejecutarse dentro de una transacción que adquiera el bloqueo de fila sobre la marca antes de calcular o escribir, y una violación de unicidad por carrera SHALL resolverse de forma determinista (rollback, relectura bajo bloqueo y reaplicación), nunca con un error de servidor.

#### Scenario: Primera edición sin DNA previo
- **WHEN** un Creator de una marca sin versiones guarda el documento
- **THEN** se crea la versión 1 en estado `DRAFT` con el documento enviado

#### Scenario: Edición con versión activa vigente
- **WHEN** un Creator de una marca con versión `ACTIVE` guarda cambios
- **THEN** se crea una nueva versión en estado `DRAFT` inicializada con el documento activo y aplicando los cambios enviados, sin modificar la versión `ACTIVE`

#### Scenario: Borrador existente se actualiza
- **WHEN** un Creator guarda cambios existiendo ya un `DRAFT` de la marca
- **THEN** el borrador se actualiza sin crear otra versión paralela

#### Scenario: Escrituras simultáneas del borrador
- **WHEN** dos solicitudes de edición del borrador de la misma marca compiten simultáneamente
- **THEN** la marca queda con un único `DRAFT` en el siguiente número de versión, la solicitud perdedora se resuelve de forma determinista bajo el mismo bloqueo y ninguna respuesta es un error de servidor

### Requirement: Publicación versionada, concurrente e idempotente
La publicación SHALL ejecutarse en una única transacción con esta secuencia obligatoria: adquirir el bloqueo de fila sobre la marca, cargar el `DRAFT` y la `ACTIVE`, transicionar la `ACTIVE` anterior a `ARCHIVED` sin modificarla y confirmar ese cambio en la base (flush), y solo entonces transicionar `DRAFT -> ACTIVE`, registrar la fecha de publicación, fijar `knowledge_status = NOT_SYNCED`, confirmar (flush) y hacer commit, dejando el documento publicado inmutable. La solicitud SHALL incluir `expected_draft_id`: la publicación repetida cuyo `expected_draft_id` coincida con la versión ya publicada SHALL tratarse como reintento idempotente devolviendo la `ACTIVE` vigente sin duplicar; cuando no coincida ni con el borrador actual ni con la `ACTIVE` vigente SHALL responder con error de transición con detalles del conflicto; cuando no exista borrador ni versión alguna SHALL responder con error de transición inválida. Una violación de unicidad por carrera SHALL resolverse de forma determinista releyendo el estado bajo el mismo mapeo (coincidencia -> reintento idempotente; discrepancia -> error de transición), nunca con un error de servidor.

#### Scenario: Primera publicación
- **WHEN** un Creator publica el borrador de una marca sin versiones activas
- **THEN** la versión pasa a `ACTIVE`, registra fecha de publicación y queda inmutable

#### Scenario: Publicación de una nueva versión
- **WHEN** un Creator publica un borrador existiendo una versión `ACTIVE` anterior
- **THEN** la nueva versión pasa a `ACTIVE`, la anterior pasa a `ARCHIVED` sin modificarse y el número de versión incrementa

#### Scenario: Reintento idempotente
- **WHEN** la publicación se repite con el `expected_draft_id` de un borrador ya publicado
- **THEN** la API devuelve la versión activa existente sin crear duplicados ni errores

#### Scenario: Publicación concurrente del mismo borrador
- **WHEN** dos solicitudes de publicación compiten sobre el mismo borrador de una marca
- **THEN** exactamente una transición se consolida, la solicitud perdedora se resuelve como reintento idempotente o como error de transición con detalles, y jamás existen dos versiones `ACTIVE` ni errores de servidor

#### Scenario: expected_draft_id desactualizado
- **WHEN** un Creator publica con un `expected_draft_id` que no corresponde al borrador actual ni a la versión activa vigente
- **THEN** la API responde con error de transición con detalles del conflicto y no cambia ningún estado

#### Scenario: Publicación sin borrador ni versión previa
- **WHEN** un Creator publica en una marca sin `DRAFT` y sin versiones
- **THEN** la API responde con error de transición inválida

### Requirement: Historial de versiones con resumen
El historial SHALL listar las versiones visibles para el rol en orden descendente con número, estado, autor, fechas de creación y publicación, estado de Knowledge y un resumen de conteos por sección del documento, sin incluir el documento completo en cada entrada. Para revisores, la lista SHALL excluir toda entrada `DRAFT`. Las versiones archivadas SHALL permanecer consultables con su documento intacto a través del detalle de versión.

#### Scenario: Listar versiones
- **WHEN** un miembro consulta las versiones del Brand DNA de su marca
- **THEN** recibe la lista ordenada con estados, fechas y conteos por sección para cada versión visible

#### Scenario: Historial sin borradores para revisores
- **WHEN** un revisor consulta el historial existiendo un `DRAFT` en curso
- **THEN** la lista contiene únicamente versiones publicadas y ninguna entrada del borrador

#### Scenario: Integridad de versiones archivadas
- **WHEN** se publica una nueva versión y se consulta una versión `ARCHIVED` anterior
- **THEN** su documento permanece idéntico al momento de su publicación

### Requirement: Estado de Knowledge según WORKFLOWS sin sincronización
Cada versión publicada SHALL persistir y exponer su estado de Knowledge. Crear o editar un borrador SHALL marcar la versión `ACTIVE` vigente cuyo estado sea `SYNCED` como `OUTDATED`, sin iniciar sincronización alguna; cuando la `ACTIVE` vigente esté en `NOT_SYNCED`, `OUTDATED` o `FAILED`, su estado SHALL permanecer sin cambio. Publicar SHALL crear la nueva versión `ACTIVE` con `NOT_SYNCED`, y la versión archivada SHALL conservar el estado que tenía. Esta capability SHALL ejecutar en ningún caso transiciones hacia `SYNCING`, `SYNCED` o `FAILED`. La interfaz SHALL presentar el estado real sin simular una sincronización inexistente.

#### Scenario: Publicación inicia no sincronizado
- **WHEN** se publica una versión
- **THEN** su `knowledge_status` es `NOT_SYNCED` y ninguna acción de esta capability lo cambia hacia `SYNCING`, `SYNCED` o `FAILED`

#### Scenario: Borrador marca la activa como desactualizada
- **WHEN** un Creator crea o edita un borrador mientras la versión `ACTIVE` vigente está `SYNCED`
- **THEN** la versión `ACTIVE` pasa a `OUTDATED` y no se inicia sincronización alguna

#### Scenario: Otros estados no cambian
- **WHEN** se crea o edita un borrador y la `ACTIVE` vigente está `NOT_SYNCED`, `OUTDATED` o `FAILED`
- **THEN** su estado permanece sin cambio

#### Scenario: Presentación honesta del estado
- **WHEN** la interfaz muestra una versión publicada por esta capability
- **THEN** presenta el estado como pendiente de sincronización (o desactualizado por cambios pendientes), sin señales de éxito de sincronización y sin afirmar la existencia de un borrador

### Requirement: Envelope de error centralizado
Toda respuesta de error de la API SHALL usar el envelope `{error: {code, message, details}}` generado por manejadores centralizados a nivel de aplicación, no por endpoint. Los manejadores SHALL traducir las `HTTPException` de FastAPI —incluidas las de los endpoints de identidad y health existentes—, las excepciones de validación de request (`RequestValidationError`, Pydantic) y los errores de dominio. Códigos exactos: 401 `UNAUTHENTICATED` para identidad ausente o inválida, 403 `PERMISSION_DENIED` para falta de membresía o rol insuficiente, 404 `NOT_FOUND` para recursos inexistentes, rutas desconocidas o no visibles por rol, 409 `INVALID_WORKFLOW_TRANSITION` para transiciones inválidas o conflictos de publicación, 422 `VALIDATION_ERROR` para requests que incumplan la validación o el contrato canónico del documento, y 503 `SERVICE_UNAVAILABLE` para dependencias esenciales no disponibles, incluyendo los casos actuales de `/health/ready` con base de datos inalcanzable y de la frontera de autenticación sin configurar. En 422, `details` SHALL listar las rutas de campo inválidas; en 409, `details` SHALL identificar el conflicto; en los códigos sin detalles adicionales, `details` SHALL ser `{}`.

#### Scenario: Error de autenticación
- **WHEN** una solicitud sin identidad válida llega a un endpoint protegido
- **THEN** responde 401 con `{error: {code: "UNAUTHENTICATED", message, details: {}}}`

#### Scenario: Error de permiso
- **WHEN** un revisor intenta escribir o un usuario sin membresía accede
- **THEN** responde 403 con `{error: {code: "PERMISSION_DENIED", message, details: {}}}`

#### Scenario: Recurso inexistente
- **WHEN** una solicitud accede a un recurso inexistente, una ruta desconocida o un revisor solicita una versión en `DRAFT`
- **THEN** responde 404 con `{error: {code: "NOT_FOUND", message, details: {}}}`

#### Scenario: Servicio no disponible
- **WHEN** `/health/ready` no alcanza la base de datos o la frontera de autenticación no está configurada
- **THEN** responde 503 con `{error: {code: "SERVICE_UNAVAILABLE", message, details: {}}}`

#### Scenario: Conflicto de transición
- **WHEN** una publicación incumple las condiciones de transición o concurrencia
- **THEN** responde 409 con `{error: {code: "INVALID_WORKFLOW_TRANSITION", message, details}}` donde `details` identifica el conflicto (p. ej. `expected_draft_id` y versión vigente)

#### Scenario: Validación canónica
- **WHEN** un documento incumple el contrato canónico
- **THEN** responde 422 con `{error: {code: "VALIDATION_ERROR", message, details}}` donde `details` lista las rutas de campo inválidas

### Requirement: Superficies frontend de Brand DNA
La aplicación web SHALL ofrecer la superficie Brand DNA (navegación de secciones con vista del documento operativo, edición del borrador, publicación y versiones), la superficie Create Brand DNA (autoría estructurada manual de las cinco secciones) y la integración en Dashboard (panel de estado del DNA y CTA de onboarding cuando no existe DNA publicado). El acceso de escritura en la interfaz SHALL reflejar el rol resolviéndose la autoridad en el backend. Toda superficie nueva SHALL incluir estados de carga, vacío, error de API y falta de permiso, conservar la jerarquía y navegación del shell por rol, y mantener las demás secciones del starter deshabilitadas como cambios futuros. Las superficies SHALL seguir la referencia visual fluffy junto con `starter-design/`: claymorphism claro y suave, tarjetas elevadas de radio amplio, panel de estado azul profundo, tiles semánticos pastel, CTA azul Steel y superficie editorial para el documento; con comportamiento responsivo en desktop y móvil, foco visible con contraste adecuado y respeto de `prefers-reduced-motion`.

#### Scenario: Creator completa el flujo de autoría
- **WHEN** un Creator sin DNA publicado entra al Dashboard y completa la creación, edición y publicación del documento
- **THEN** pasa de CTA de onboarding a panel de estado con versión activa y refleja el resultado en Brand DNA y Dashboard

#### Scenario: Revisor en modo solo lectura
- **WHEN** un revisor abre Brand DNA o Dashboard
- **THEN** ve el DNA publicado con sus estados y navegación de rol, sin controles de creación, edición ni publicación

#### Scenario: Estados no ideales
- **WHEN** una superficie de Brand DNA está cargando, sin datos, recibe un error de API o un error de permiso
- **THEN** presenta un estado comprensible que conserva la jerarquía visual y permite reintentar o volver

#### Scenario: Responsivo y accesibilidad visual
- **WHEN** las superficies se usan en desktop y móvil con navegación por teclado
- **THEN** conservan la jerarquía de `starter-design/`, el foco es visible con contraste adecuado y el movimiento respeta `prefers-reduced-motion`
