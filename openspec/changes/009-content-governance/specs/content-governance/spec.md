## Purpose

Regula la revisión semántica humana de Creative: una máquina de estados protegida en backend (`DRAFT → PENDING_CONTENT_REVIEW → CONTENT_CHANGES_REQUESTED ↔ PENDING_CONTENT_REVIEW → CONTENT_APPROVED`), cola real para Content Reviewer, decisiones inmutables que referencian la versión exacta enviada e history append-only con actor, evento y tiempo.

## ADDED Requirements

### Requirement: Máquina de estados de revisión semántica protegida en backend
El sistema SHALL mantener el estado de revisión semántica de cada creative item como `workflow_status` con valores `DRAFT`, `PENDING_CONTENT_REVIEW`, `CONTENT_CHANGES_REQUESTED` y `CONTENT_APPROVED`. Toda transición SHALL validarse y persistirse solo en backend: el frontend MUST NOT ser autoridad de ninguna transición ni enviar el estado destino como dato confiable. Las transiciones válidas son exclusivamente: `DRAFT → PENDING_CONTENT_REVIEW` (submit), `PENDING_CONTENT_REVIEW → CONTENT_CHANGES_REQUESTED` (request changes), `CONTENT_CHANGES_REQUESTED → PENDING_CONTENT_REVIEW` (resubmit con versión nueva) y `PENDING_CONTENT_REVIEW → CONTENT_APPROVED` (approve). Cualquier otra transición solicitada MUST responder 409 con el envelope de error existente, sin mutar estado, decisiones ni eventos. Cada command SHALL validar brand membership del actor sobre el ítem antes de evaluar cualquier otra condición (403 membership-first si no hay membresía).

#### Scenario: Transición inválida rechazada
- **WHEN** se solicita aprobar un ítem cuyo `workflow_status` es `DRAFT` o `CONTENT_CHANGES_REQUESTED`
- **THEN** la respuesta es 409 con envelope, y el estado, las decisiones y los eventos permanecen sin cambios

#### Scenario: Estado nunca viene del cliente
- **WHEN** una request incluye un estado o flag de workflow en su payload
- **THEN** el sistema ignora ese dato para decidir la transición: la autoridad es exclusivamente el estado persistido en backend

#### Scenario: Actor sin membresía de la marca
- **WHEN** un usuario sin membresía en la marca del ítem invoca cualquier endpoint de Content Review o submit
- **THEN** la respuesta es 403 con envelope, evaluada antes de resolver el recurso o su estado

### Requirement: Submit de versión exacta y congelada
El sistema SHALL permitir al Creator enviar una `creative_version` exacta de su creative item, referenciándola como la versión enviada (`submitted_version_id`). El submit SHALL exigir rol `CREATOR`, que la versión pertenezca al ítem y que el estado del ítem sea `DRAFT` o `CONTENT_CHANGES_REQUESTED`. El submit desde `CONTENT_CHANGES_REQUESTED` SHALL exigir que la versión enviada sea distinta (número de versión mayor) a la última versión enviada de ese ítem. La transición a `PENDING_CONTENT_REVIEW` y el registro del `workflow_event` correspondiente SHALL persistirse en la misma transacción de base de datos: o ambos se comprometen o ninguno. La versión enviada queda congelada: el sistema MUST NOT modificar su brief, output, contexto aplicado, score ni trace tras el envío; cualquier cambio humano o regeneración produce una versión nueva (regla de versionado inmutable de Creative).

#### Scenario: Submit desde DRAFT
- **WHEN** un Creator envía la versión actual de un ítem en `DRAFT`
- **THEN** el ítem pasa a `PENDING_CONTENT_REVIEW`, la versión queda referenciada como enviada y existe un `workflow_event` de submit con actor y timestamp

#### Scenario: Reenvío exige versión nueva
- **WHEN** un Creator reenvía un ítem en `CONTENT_CHANGES_REQUESTED` seleccionando la misma versión que fue rechazada
- **THEN** la respuesta es 409 con envelope y el ítem permanece en `CONTENT_CHANGES_REQUESTED`

#### Scenario: Reenvío con versión nueva
- **WHEN** un Creator crea una versión nueva y la envía desde `CONTENT_CHANGES_REQUESTED`
- **THEN** el ítem pasa a `PENDING_CONTENT_REVIEW` referenciando la versión nueva y se registra el evento de submit

#### Scenario: Submit por rol no Creator
- **WHEN** un Content Reviewer o Visual Reviewer intenta enviar un ítem
- **THEN** la respuesta es 403 con envelope y no se produce transición ni evento

#### Scenario: La versión enviada no cambia
- **WHEN** el ciclo de revisión avanza (request changes, reenvío, aprobación)
- **THEN** el brief, output, contexto aplicado, score y trace de cada versión enviada permanecen exactamente como fueron persistidos al momento del envío

### Requirement: Cola de revisión para Content Reviewer
El sistema SHALL exponer una cola de revisión que liste, para las marcas donde el actor tiene rol `CONTENT_REVIEWER`, los creative items en `PENDING_CONTENT_REVIEW` con su marca, tipo, título, versión enviada y timestamp de entrada a la cola. El orden de la cola SHALL ser determinista y reproducible (timestamp del evento de submit más reciente del ítem ascendente, desempate por id ascendente). Otros roles con membresía no pueden decidir pero MAY leer la cola de sus marcas. La cola solo devuelve ítems de marcas donde el actor tiene membresía: la respuesta MUST NOT filtrar por marca enviada por el cliente como mecanismo de autorización (el filtro del cliente solo acota, nunca amplía).

#### Scenario: Cola para Content Reviewer
- **WHEN** un Content Reviewer consulta la cola
- **THEN** la respuesta incluye solo ítems `PENDING_CONTENT_REVIEW` de sus marcas, ordenados deterministamente por tiempo de entrada a la cola

#### Scenario: Aislamiento por membresía
- **WHEN** un Content Reviewer de la marca A consulta la cola existiendo ítems pendientes de la marca B
- **THEN** la respuesta no incluye ningún ítem de la marca B

#### Scenario: Ítems decididos salen de la cola
- **WHEN** un ítem pendiente recibe una decisión (approve o request changes)
- **THEN** deja de aparecer en la cola en la consulta siguiente

### Requirement: Detalle de revisión con versión congelada y contexto aplicado
El sistema SHALL exponer el detalle de revisión de un creative item en revisión: la versión exacta enviada (brief, output, consistencia y trace vinculados a esa versión), el contexto de Brand Knowledge aplicado en su generación según lo ya persistido por Creative, el estado del workflow y el feedback de decisiones previas. La revisión MUST NOT invocar modelos de IA ni re-consultar Brand Knowledge: todo lo presentado es evidencia ya persistida. El Content Reviewer y el Creator con membresía pueden leer el detalle; un Creator MUST NOT obtener de este detalle capacidades de edición.

#### Scenario: Detalle para revisar
- **WHEN** un Content Reviewer abre el detalle de un ítem `PENDING_CONTENT_REVIEW`
- **THEN** la respuesta muestra la versión enviada congelada, el contexto aplicado persistido, el estado y el feedback previo, sin ejecutar generación ni retrieval

#### Scenario: Detalle de ítem inexistente o ajeno
- **WHEN** se consulta el detalle de un ítem que no existe o de una marca sin membresía
- **THEN** la respuesta es 404 o 403 respectivamente con envelope, según el orden membership-first

### Requirement: Decisión de aprobación semántica
El sistema SHALL permitir aprobar un creative item solo a un actor con rol `CONTENT_REVIEWER` y solo cuando el `workflow_status` es `PENDING_CONTENT_REVIEW`. La aprobación SHALL persistir en la misma transacción: la decisión en `content_reviews` referenciando la `submitted_version_id` exacta y el actor, la transición a `CONTENT_APPROVED` y el `workflow_event` de decisión. El Creator del contenido MUST recibir 403 aunque sea miembro de la marca; el Visual Reviewer también recibe 403 (la aprobación visual pertenece a otra capability). Un intento desde estado distinto de `PENDING_CONTENT_REVIEW` responde 409 sin efectos. La decisión es inmutable: el sistema MUST NOT permitir editar o borrar una decisión persistida.

#### Scenario: Aprobación exitosa
- **WHEN** un Content Reviewer aprueba un ítem `PENDING_CONTENT_REVIEW`
- **THEN** el ítem pasa a `CONTENT_APPROVED`, existe una decisión `APPROVED` que referencia la versión enviada exacta y el actor, y se registra el `workflow_event` correspondiente

#### Scenario: Creator no aprueba su contenido
- **WHEN** el Creator que envió el ítem (u otro Creator de la marca) intenta aprobarlo
- **THEN** la respuesta es 403 con envelope y no se persiste decisión, transición ni evento

#### Scenario: Aprobación desde estado inválido
- **WHEN** se intenta aprobar un ítem que ya está `CONTENT_APPROVED` o `CONTENT_CHANGES_REQUESTED`
- **THEN** la respuesta es 409 con envelope y no se duplican decisiones ni eventos

### Requirement: Solicitud de cambios con feedback
El sistema SHALL permitir solicitar cambios solo a un `CONTENT_REVIEWER` y solo desde `PENDING_CONTENT_REVIEW`, con feedback textual obligatorio registrado junto a la decisión `CHANGES_REQUESTED` que referencia la versión enviada exacta. La transición a `CONTENT_CHANGES_REQUESTED`, la decisión y el `workflow_event` se persisten en la misma transacción. El reenvío posterior solo es posible con una versión nueva; la versión rechazada y su feedback quedan como evidencia inmutable.

#### Scenario: Solicitud de cambios exitosa
- **WHEN** un Content Reviewer solicita cambios con feedback sobre un ítem `PENDING_CONTENT_REVIEW`
- **THEN** el ítem pasa a `CONTENT_CHANGES_REQUESTED`, la decisión con feedback referencia la versión enviada y se registra el evento

#### Scenario: Feedback ausente
- **WHEN** se solicita cambios sin feedback
- **THEN** la respuesta es de validación con envelope, sin transición ni decisión persistida

### Requirement: Idempotencia de decisiones ante retry
Los commands de decisión SHALL tolerar reintentos: reintentar la misma decisión (approve o request changes) sobre un ítem cuya versión enviada ya recibió esa misma decisión en la misma dirección responde con el resultado vigente sin duplicar decisiones, eventos ni transiciones. Un retry concurrente sobre el mismo ítem pendiente deja exactamente una decisión y un evento: el sistema SHALL resolverlo con un claim condicional atómico sobre el estado (`PENDING_CONTENT_REVIEW`) de forma que un solo retry gana y el resto lee el resultado persistido. Decidir en dirección contraria sobre la misma versión enviada (p. ej. request changes tras aprobar esa versión) responde 409 sin efectos.

#### Scenario: Retry de approve idempotente
- **WHEN** un Content Reviewer reintenta approve sobre un ítem ya `CONTENT_APPROVED` por esa misma versión
- **THEN** la respuesta devuelve el estado vigente sin crear una segunda decisión ni un segundo evento

#### Scenario: Retry concurrente del mismo comando
- **WHEN** dos approve simultáneos llegan sobre el mismo ítem `PENDING_CONTENT_REVIEW`
- **THEN** exactamente uno gana el claim atómico y completa; el otro responde con el resultado vigente sin duplicar decisión ni evento

#### Scenario: Decisión en dirección contraria
- **WHEN** se solicita request changes sobre un ítem ya `CONTENT_APPROVED` con esa misma versión enviada
- **THEN** la respuesta es 409 con envelope y no se persiste nada

### Requirement: History append-only con actor, evento y tiempo
El sistema SHALL registrar cada submit y cada decisión como `workflow_event` append-only del creative item, con tipo de evento, actor (nullable para eventos del sistema), metadata sanitizada y timestamp. El history SHALL exponerse ordenado cronológicamente ascendente y refleja el ciclo completo del ítem, incluidos reenvíos con versiones nuevas y decisiones sobre versiones anteriores. El sistema MUST NOT ofrecer ninguna vía de actualización o borrado de eventos: el repositorio de dominio solo inserta y lee. La metadata de los eventos MUST NOT duplicar el contenido enviado ni datos sensibles: referencia la versión y la decisión, no el output.

#### Scenario: Timeline del ciclo completo
- **WHEN** un ítem recorre submit → request changes → versión nueva → submit → approve y se consulta su history
- **THEN** los eventos aparecen en orden cronológico con actor, tipo y timestamp, reflejando cada paso sin huecos

#### Scenario: Eventos inmutables
- **WHEN** se auditan las operaciones disponibles sobre `workflow_events`
- **THEN** no existe ninguna ruta de actualización o borrado: solo inserción y lectura

### Requirement: Visibilidad de estado y feedback por rol
El sistema SHALL exponer al Creator el estado del workflow de sus ítems y el feedback de las decisiones recibidas, sin otorgar capacidades de edición sobre la versión enviada. El Content Reviewer ve estado, decisiones y timeline de los ítems de sus marcas. La UI de Approvals solo se activa para `CONTENT_REVIEWER`; la UI de Creative Studio muestra al Creator estado y feedback como lectura. Ninguna superficie de revisión ofrece controles de edición de contenido.

#### Scenario: Creator observa feedback
- **WHEN** un Creator consulta un ítem suyo en `CONTENT_CHANGES_REQUESTED`
- **THEN** ve el estado y el feedback de la decisión recibida, y ninguna acción de edición actúa sobre la versión enviada

#### Scenario: Approvals solo para Content Reviewer
- **WHEN** un Creator o Visual Reviewer navega
- **THEN** la entrada de navegación Approvals no está disponible para su rol
