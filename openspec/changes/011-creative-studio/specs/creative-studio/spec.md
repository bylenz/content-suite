## Purpose

Regula la autoría de contenido creativo antes de entrar a revisión: creación y lectura de creative items y sus versiones, la ventana en la que su contenido puede autorarse (manualmente o vía IA), la generación asistida por IA con citas de reglas verificadas contra el contexto de Brand Knowledge realmente recuperado, y el consistency-check con score calculado en backend. No regula la máquina de estados de revisión semántica ni visual (propiedad de `content-governance` y `visual-compliance` respectivamente): esta capability solo gobierna lo que ocurre en `DRAFT` y `CONTENT_CHANGES_REQUESTED`, antes de que exista una versión enviada a revisión.

## ADDED Requirements

### Requirement: Creación de creative items
El sistema SHALL permitir a un Creator con membresía en la marca crear un creative item de un `type` fijo (`product_description`, `video_script`, `image_prompt`) con `title` y un `brief` opcional. La creación SHALL sembrar la primera versión (`version=1`, origen `HUMAN_EDIT`, sin `output`) en estado `DRAFT`, capturando la versión de Brand DNA activa de la marca en ese momento si existe. El `type` del item queda fijo desde la creación: ninguna versión posterior puede cambiarlo.

#### Scenario: Creación válida
- **WHEN** un Creator con membresía crea un item con `type`, `title` y `brief`
- **THEN** el item queda `DRAFT` con una versión 1 (`HUMAN_EDIT`, ese brief, `output` vacío) y la versión de Brand DNA activa de la marca capturada si existe

#### Scenario: Tipo desconocido o campo no reconocido
- **WHEN** la request de creación incluye un `type` fuera del enum o un campo no reconocido por el contrato
- **THEN** la respuesta es de validación y no se crea ningún item

### Requirement: Lectura sin fuga de existencia
El sistema SHALL permitir a cualquier miembro de la marca (`CREATOR`, `CONTENT_REVIEWER`, `VISUAL_REVIEWER`) leer los creative items de sus marcas, el detalle de un item con su versión más reciente, el listado de versiones de un item y el detalle de una versión específica. Toda lectura SHALL resolver membresía antes que cualquier otra condición: un item inexistente y un item de una marca sin membresía del actor MUST responder exactamente igual (404), sin revelar cuál de las dos situaciones ocurrió. Una versión solicitada que no pertenece al item de la ruta responde 404.

#### Scenario: Lectura por cualquier rol con membresía
- **WHEN** un `CONTENT_REVIEWER` o `VISUAL_REVIEWER` con membresía en la marca consulta un item, su listado de versiones o el detalle de una versión
- **THEN** la respuesta es exitosa, sin exigir rol `CREATOR`

#### Scenario: Item inexistente o marca sin membresía
- **WHEN** se consulta un item que no existe o un item de una marca donde el actor no tiene membresía
- **THEN** ambos casos responden 404 con el mismo envelope

#### Scenario: Versión de otro item
- **WHEN** se solicita el detalle de una versión que pertenece a un item distinto al de la ruta
- **THEN** la respuesta es 404

### Requirement: Escritura restringida a Creator con membresía
Crear, editar, generar, regenerar y auditar consistencia SHALL exigir rol `CREATOR` con membresía en la marca. Un miembro de la marca con rol `CONTENT_REVIEWER` o `VISUAL_REVIEWER` MUST recibir 403 al intentar cualquiera de estas acciones. Para acciones sobre un item ya existente (editar, generar, regenerar, auditar consistencia), la membresía se evalúa junto con la existencia del item antes que cualquier otra condición: un actor sin membresía en la marca de ese item MUST recibir 404, igual que si el item no existiera, para no revelar cuál de las dos situaciones ocurrió. La creación no tiene un item que proteger de esa fuga: un actor sin membresía en la marca indicada al crear MUST recibir 403, igual que un miembro con rol distinto de `CREATOR`.

#### Scenario: Rol de revisor rechazado
- **WHEN** un `CONTENT_REVIEWER` o `VISUAL_REVIEWER` con membresía en la marca intenta crear, editar, generar, regenerar o auditar consistencia
- **THEN** la respuesta es 403 y no se persiste ningún cambio

#### Scenario: Sin membresía en la marca al crear
- **WHEN** un usuario sin membresía en la marca indicada intenta crear un item
- **THEN** la respuesta es 403

#### Scenario: Sin membresía en la marca de un item existente
- **WHEN** un usuario sin membresía en la marca de un item existente intenta editarlo, generar, regenerar o auditar su consistencia
- **THEN** la respuesta es 404, igual que si el item no existiera

### Requirement: Ventana editable y versionado inmutable
El sistema SHALL restringir la creación de nuevas versiones (edición manual, generación, regeneración) a los estados `DRAFT` y `CONTENT_CHANGES_REQUESTED`: cualquier intento en otro estado responde 409 sin persistir nada. Cada versión nueva SHALL insertarse con el siguiente número consecutivo (`max_version + 1`) bajo un lock de fila del item. Ninguna versión existente SHALL modificarse tras su creación, salvo la proyección de auditoría que persiste el consistency-check (resultado y score), que MUST NOT tocar brief, output ni `applied_rule_ids`. Una edición manual SHALL validar que el `content_type` del output coincida con el `type` fijo del item, y SHALL reusar el brief de la versión anterior cuando no se provee uno nuevo explícito.

#### Scenario: Edición o generación fuera de la ventana editable
- **WHEN** se intenta editar, generar o regenerar sobre un item en `PENDING_CONTENT_REVIEW`, `CONTENT_APPROVED` o cualquier estado posterior
- **THEN** la respuesta es 409 y no se crea versión

#### Scenario: content_type inconsistente
- **WHEN** una edición manual envía un output cuyo `content_type` no coincide con el `type` del item
- **THEN** la respuesta es de validación y no se persiste la versión

#### Scenario: Brief no provisto reusa el anterior
- **WHEN** una edición manual no incluye `brief`
- **THEN** la nueva versión conserva el `brief` de la versión anterior del item

### Requirement: Validación estricta y límite de tamaño del brief
El sistema SHALL rechazar, tanto en creación como en edición manual, cualquier payload con campos no reconocidos o valores fuera de los enums declarados. El `brief` serializado SHALL limitarse a 16&nbsp;KB en ambas operaciones; excederlo responde con error de validación sin persistir cambio alguno.

#### Scenario: Brief que excede el límite
- **WHEN** el `brief` serializado de una creación o edición supera 16&nbsp;KB
- **THEN** la respuesta es de validación y no se crea ni modifica ninguna versión

### Requirement: Generación y regeneración asistida por IA con citas verificadas
El sistema SHALL generar una nueva versión (origen `AI_GENERATED`, o `AI_REGENERATED` en regeneración) invocando la capability de IA correspondiente al `type` del item con el contexto híbrido recuperado de Brand Knowledge de esa marca. La generación SHALL exigir que la versión de Brand DNA activa de la marca tenga `knowledge_status = SYNCED`; cualquier otro estado (incluido `OUTDATED`) responde 503 sin persistir versión. Sin un proveedor de texto configurado, responde 503. Los `applied_rule_ids` que el modelo cite SHALL verificarse server-side contra las reglas efectivamente recuperadas en el contexto: una cita que no está en el contexto recuperado se descarta; si ninguna cita sobrevive la verificación, el sistema usa el conjunto completo de reglas mandatorias como piso — el sistema MUST NOT persistir una referencia fabricada por el modelo. Una salida que no valida contra el contrato estructurado del `type` no persiste versión alguna.

#### Scenario: Generación exitosa dentro de la ventana editable
- **WHEN** un Creator genera sobre un item `DRAFT` o `CONTENT_CHANGES_REQUESTED` con Brand DNA `SYNCED` y proveedor de texto configurado
- **THEN** se crea una versión `AI_GENERATED` cuyos `applied_rule_ids` están limitados a citas verificadas contra el contexto recuperado

#### Scenario: Brand DNA no sincronizada
- **WHEN** la versión de Brand DNA activa de la marca no está `SYNCED` (incluido `OUTDATED`)
- **THEN** la generación responde 503 y no se persiste versión

#### Scenario: Cita fabricada descartada
- **WHEN** el modelo cita un `rule_id` que no existe en el contexto recuperado
- **THEN** esa cita se descarta y, si ninguna cita sobrevive, la versión persiste con el conjunto mandatorio completo como `applied_rule_ids`

#### Scenario: Salida inválida no persiste nada
- **WHEN** la respuesta del modelo no valida contra el contrato estructurado del `type`
- **THEN** no se crea ninguna versión

### Requirement: Consistency-check con score calculado en backend
El sistema SHALL permitir a un Creator auditar la consistencia de la última versión de un item contra las reglas de marca, exigiendo que esa versión tenga `output`; sin `output` responde 422. La auditoría SHALL usar el mismo contexto híbrido de Brand Knowledge y exigir Brand DNA `SYNCED`, igual que la generación. El score de consistencia SHALL calcularse en backend a partir de los checks estructurados devueltos por el modelo — el sistema MUST NOT aceptar un score provisto directamente por el modelo. El resultado SHALL persistirse únicamente en la proyección de auditoría de esa versión (`consistency_result`, `consistency_score`, trace), sin modificar su brief, output, `applied_rule_ids` ni `brand_dna_version_id`. Esta operación MUST NOT producir ninguna transición de workflow.

#### Scenario: Check exitoso persiste solo la proyección de auditoría
- **WHEN** un Creator ejecuta consistency-check sobre la última versión de un item que tiene `output`
- **THEN** se persisten resultado y score calculado en backend en esa versión, sin alterar su contenido ni el estado del item

#### Scenario: Sin contenido que auditar
- **WHEN** se ejecuta consistency-check sobre una versión sin `output`
- **THEN** la respuesta es 422 y no se persiste resultado

### Requirement: Contexto aplicado siempre relativo a la última versión
El sistema SHALL exponer, para cada item, el contexto aplicado (número de versión, id de versión, versión de Brand DNA vinculada y `applied_rule_ids`) de su versión más reciente, nunca de una versión histórica. El campo de versión de Brand DNA SHALL ser nulo si la marca no tenía Brand DNA activa publicada al momento de la versión vigente.

#### Scenario: Contexto sigue a la versión vigente
- **WHEN** un item recibe una versión nueva (edición, generación o regeneración)
- **THEN** el contexto aplicado consultado después refleja esa versión nueva, no la anterior

#### Scenario: Sin Brand DNA publicada
- **WHEN** la marca del item no tiene una versión de Brand DNA activa
- **THEN** el contexto aplicado devuelve `brand_dna_version_id` nulo
