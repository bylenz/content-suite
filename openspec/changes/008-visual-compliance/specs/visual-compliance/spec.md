## Purpose

Versiona visuales ligados a creative items aprobados, los audita multimodalmente contra Brand Knowledge visual obligatorio con findings estructurados y score determinista, y deja la decisión final exclusivamente en manos del Visual Compliance Reviewer, con excepciones HIGH explícitas y auditadas.

## ADDED Requirements

### Requirement: Versionado inmutable de visuales ligados al creative item aprobado
El sistema SHALL aceptar el upload de un visual únicamente para un creative item en estado `CONTENT_APPROVED`, subido por un Creator miembro de la marca del item; cualquier otro estado SHALL responder 409 y cualquier falta de rol o membresía 403. Cada upload SHALL crear una nueva versión de visual asset (`UNIQUE(creative_item_id, version)`) y el primer visual SHALL transicionar el item a `PENDING_VISUAL_REVIEW` registrando `workflow_event`. Un visual ya auditado o referenciado por una auditoría o decisión MUST NOT sobrescribirse ni mutar: una corrección crea siempre una versión nueva y las correcciones sobre `VISUAL_CHANGES_REQUESTED` reabren `PENDING_VISUAL_REVIEW` con la nueva versión.

#### Scenario: Upload sobre item aprobado
- **WHEN** un Creator sube un visual válido para un item `CONTENT_APPROVED`
- **THEN** se crea la versión 1 del visual asset, el item pasa a `PENDING_VISUAL_REVIEW` y se registra el workflow event correspondiente

#### Scenario: Upload en estado inválido
- **WHEN** se intenta subir un visual para un item que no está en `CONTENT_APPROVED` ni en `VISUAL_CHANGES_REQUESTED` según el flujo acordado
- **THEN** la respuesta es 409 con envelope y no se crea ninguna versión

#### Scenario: Corrección crea versión nueva
- **WHEN** tras un `request-changes` el Creator sube un visual corregido
- **THEN** se crea una versión nueva del asset, la versión anterior permanece intacta con sus auditorías y el item vuelve a `PENDING_VISUAL_REVIEW`

#### Scenario: Versión auditada nunca muta
- **WHEN** se compara un visual asset que ya tiene auditorías con cualquier estado posterior del item
- **THEN** su contenido, ruta de storage y metadata persistidos no han cambiado

### Requirement: Auditoría multimodal con contexto visual obligatorio y fail-safe
El sistema SHALL ejecutar la auditoría de un visual invocando el puerto `VisionModel` de AI Platform únicamente desde el service de dominio del módulo visual audit, nunca desde routers, y siempre con contexto visual construido por Knowledge (006) que incluya todas las reglas mandatory aplicables al scope `VISUAL`/`BOTH` de la versión Brand DNA del item. Si el contexto visual obligatorio no está disponible (sin versión ACTIVE servible, sin mandatory aplicables, adapter de consulta ausente o incompatible), la auditoría SHALL fallar seguro con 503 sin llamar al modelo, sin findings parciales y sin cambiar estados de workflow. La auditoría queda persistida referenciando el visual asset exacto, la versión Brand DNA usada y el contexto aplicado; re-ejecutar la auditoría de un asset crea un registro nuevo y no muta los existentes.

#### Scenario: Audit exitosa con Knowledge visual disponible
- **WHEN** se ejecuta la auditoría de un visual con la versión Brand DNA servible y mandatory visual presente
- **THEN** se invoca el VisionModel con el contexto visual aplicado y se persiste la auditoría con findings, score, summary, referencia a asset y versión Brand DNA, y trace ID

#### Scenario: Fail-safe sin Knowledge obligatorio
- **WHEN** se solicita una auditoría y la versión Brand DNA no está servible o carece de reglas mandatory visuales aplicables
- **THEN** la respuesta es 503 con envelope, no se invoca el VisionModel, no se persiste ninguna auditoría parcial y el workflow del item no cambia

#### Scenario: Auditoría sin mutación de previas
- **WHEN** se re-ejecuta la auditoría del mismo visual asset
- **THEN** se crea un registro de auditoría nuevo y las auditorías previas permanecen idénticas

### Requirement: Findings estructurados y score determinista calculado en backend
Los findings de cada auditoría SHALL validar un contrato Pydantic con `rule_id/category/severity/status/expected/detected/evidence/recommendation`; un output del modelo que viole el contrato SHALL invalidar la auditoría con error controlado (503 hacia el cliente, registrada de forma sanitizada) sin persistir findings inválidos ni decidir nada. El backend SHALL calcular el score como función determinista pura de los findings persistidos (penalizaciones por severidad, sin aleatoriedad ni dependencia del modelo) y persistirlo junto a los findings. El score y los findings MUST NOT aprobar ni rechazar automáticamente nada: son evidencia para la decisión humana.

#### Scenario: Contrato de findings inválido
- **WHEN** el VisionModel devuelve un output que no satisface el contrato de findings (falta un campo, severidad fuera del enum, estructura incorrecta)
- **THEN** la auditoría falla con 503 controlado, no se persiste ninguna auditoría con findings inválidos y el error queda registrado sin contenido crudo del prompt

#### Scenario: Score determinista
- **WHEN** dos auditorías sobre el mismo asset producen el mismo conjunto de findings
- **THEN** el score calculado y persistido por el backend es idéntico en ambos casos, sin intervención del proveedor de IA

#### Scenario: El score no decide
- **WHEN** una auditoría produce el score máximo posible
- **THEN** el item no transiciona a `FINAL_APPROVED` y la aprobación solo ocurre por decisión explícita del Visual Compliance Reviewer

### Requirement: Decisión final exclusiva del Visual Compliance Reviewer con excepción HIGH auditada
Solo un `VISUAL_REVIEWER` miembro de la marca SHALL poder aprobar o solicitar cambios sobre una auditoría; cualquier otro rol SHALL recibir 403. Las decisiones SHALL crearse como registros inmutables que referencian la auditoría exacta (`APPROVED`/`CHANGES_REQUESTED`, feedback opcional) y SHALL registrarse como `workflow_event` append-only. Aprobar existiendo findings HIGH SHALL requerir explícitamente `exception_accepted=true` con la evidencia del finding persistida en la decisión; aprobar sin marcar la excepción ante un HIGH SHALL rechazarse con 422. `CHANGES_REQUESTED` transiciona el item a `VISUAL_CHANGES_REQUESTED` y exige una versión visual nueva para reintentar; `APPROVED` transiciona a `FINAL_APPROVED` y cierra el flujo. El reviewer visual MUST NOT modificar Brand DNA ni contenido en ningún comando de esta capability.

#### Scenario: Solo el Visual Reviewer decide
- **WHEN** un Creator o Content Reviewer intenta aprobar o solicitar cambios sobre una auditoría
- **THEN** la respuesta es 403 con envelope y no se crea ninguna decisión ni evento

#### Scenario: Aprobación con HIGH sin excepción
- **WHEN** el Visual Reviewer aprueba una auditoría con findings HIGH sin enviar `exception_accepted=true`
- **THEN** la respuesta es 422 con envelope, no se crea la decisión y el item permanece en `PENDING_VISUAL_REVIEW`

#### Scenario: Aprobación con excepción explícita
- **WHEN** el Visual Reviewer aprueba con `exception_accepted=true` ante findings HIGH
- **THEN** se persiste la decisión con la excepción, el actor, el timestamp y la evidencia del finding, el item pasa a `FINAL_APPROVED` y el evento queda registrado

#### Scenario: Request changes exige versión nueva
- **WHEN** el Visual Reviewer solicita cambios y se reintenta aprobar sin nueva versión visual
- **THEN** el flujo permanece en `VISUAL_CHANGES_REQUESTED` hasta que una versión nueva reabra `PENDING_VISUAL_REVIEW`, y la decisión previa no se modifica

### Requirement: Endpoints Visual Review con RBAC backend y orden membership-first
El sistema SHALL exponer los endpoints de Visual Review de `API.md`: cola del reviewer, upload y listado de visual assets por creative item, disparo y lectura de auditoría por asset, approve y request-changes por auditoría, e historial visual por item. Toda comprobación SHALL resolver primero membresía y rol (403 antes de evaluar cualquier recurso), continuando con 404 para recurso inexistente o ajeno a la marca y 409 para estados de workflow inválidos. Los errores SHALL normalizarse con el envelope centralizado (403/404/409/422/503) y los comandos de decisión SHALL tolerar retry idempotente (repetir la misma decisión sobre la misma auditoría no crea decisiones duplicadas).

#### Scenario: Cola del Visual Reviewer
- **WHEN** un Visual Compliance Reviewer consulta su cola
- **THEN** recibe los items de su marca en `PENDING_VISUAL_REVIEW` con su visual vigente y estado de auditoría, y solo recursos de marcas donde es miembro

#### Scenario: Orden membership-first
- **WHEN** un usuario sin membresía consulta cualquier endpoint de Visual Review, exista o no el recurso
- **THEN** la respuesta es 403 antes de resolver el recurso solicitado

#### Scenario: Decisión idempotente
- **WHEN** la misma decisión de aprobación se reenvía por retry sobre la misma auditoría con el mismo payload
- **THEN** no se duplican decisiones ni workflow events y la respuesta es consistente con la primera

#### Scenario: Errores normalizados
- **WHEN** cualquier endpoint de Visual Review falla por permiso, recurso inexistente, transición inválida, contrato inválido o servicio no disponible
- **THEN** la respuesta usa el envelope centralizado con el código y estado HTTP correspondientes

### Requirement: Trazabilidad sanitizada de upload y auditoría
El sistema SHALL trazar el upload y la auditoría visual a través del puerto `Tracer` de observabilidad (005), con la versión del visual, la versión Brand DNA, el modelo y prompt version usados, la latencia y el resultado estructurado (conteos de findings y score). Los errores SHALL sanitizarse al nombre de la clase de excepción y los spans MUST NOT contener imágenes, prompts, respuestas crudas, findings completos ni secretos. El fallo del tracer SHALL degradar sin romper la operación de dominio.

#### Scenario: Spans de upload y audit
- **WHEN** se sube un visual y se ejecuta su auditoría
- **THEN** se emiten spans diferenciados con identidad de asset/versión, versión Brand DNA, modelo, latencia y conteos, sin payloads crudos

#### Scenario: Fallo del tracer
- **WHEN** el tracer falla durante un upload o una auditoría
- **THEN** la operación de dominio completa normalmente y el fallo queda registrado de forma sanitizada
