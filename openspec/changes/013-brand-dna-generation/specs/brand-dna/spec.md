## ADDED Requirements

### Requirement: Generación del borrador desde un brief estructurado
El sistema SHALL permitir a un Creator con membresía en la marca generar el DRAFT de Brand DNA a partir de un brief estructurado (datos básicos de marca, audiencia, personalidad/tono, reglas de marca siempre/nunca), invocando la AI Platform para producir las cinco secciones del `BrandDnaDocument` completo en una sola generación. La generación MUST NOT depender de Brand Knowledge sincronizada de ninguna forma: a diferencia de la generación de Creative Studio, no existe contexto de retrieval que recuperar en este punto del ciclo de vida (Knowledge se deriva de Brand DNA, nunca al revés).

#### Scenario: Generación exitosa sobre marca sin Brand DNA previa
- **WHEN** un Creator con membresía envía un brief válido a una marca que aún no tiene ninguna versión de Brand DNA
- **THEN** se crea el DRAFT (versión 1) con el documento generado y el brief que lo originó

#### Scenario: Generación no requiere Knowledge sincronizada
- **WHEN** se genera un borrador para una marca cuya Brand DNA `ACTIVE` (si existe) no tiene Knowledge `SYNCED`
- **THEN** la generación procede igualmente: esta operación no evalúa ni exige `knowledge_status`

### Requirement: Misma vía de persistencia que la autoría manual
El documento generado SHALL persistirse exactamente por el mismo camino que ya usa la autoría manual del DRAFT (upsert bajo lock de marca): si ya existe un DRAFT, la generación lo reemplaza en el mismo registro de versión; si no existe, crea la siguiente versión. El efecto de marcar la versión `ACTIVE` como `OUTDATED` cuando estaba `SYNCED` SHALL aplicarse igual que en la autoría manual, sin lógica adicional específica de generación.

#### Scenario: Generación sobre un DRAFT existente lo reemplaza
- **WHEN** un Creator genera un borrador nuevo mientras ya existe un DRAFT de la marca
- **THEN** el documento y el brief del DRAFT se reemplazan en la misma versión, sin crear una versión adicional

#### Scenario: Generación marca la ACTIVE como OUTDATED
- **WHEN** se genera un borrador para una marca cuya versión `ACTIVE` tiene Knowledge `SYNCED`
- **THEN** esa versión `ACTIVE` pasa a `OUTDATED`, igual que produciría un `PATCH /draft` manual

### Requirement: Falla segura del proveedor y validación estricta de la salida
Sin un proveedor de texto configurado, la generación SHALL responder 503 sin crear ni modificar ningún DRAFT. Una salida del modelo que no valide contra el contrato estructurado SHALL descartarse sin persistir cambio alguno: el DRAFT (o su ausencia) queda exactamente como estaba antes del intento.

#### Scenario: Proveedor no configurado
- **WHEN** se solicita generación sin un proveedor de texto configurado
- **THEN** la respuesta es 503 y el estado de Brand DNA de la marca no cambia

#### Scenario: Salida inválida no persiste
- **WHEN** la respuesta del modelo no valida contra el contrato estructurado de generación
- **THEN** no se crea ni modifica ningún DRAFT

### Requirement: Autorización exclusiva del Creator
Generar el borrador SHALL exigir rol `CREATOR` con membresía en la marca — el mismo gate que ya exige `PATCH /draft` y `POST /publish`. Un miembro con otro rol SHALL recibir 403; un actor sin membresía SHALL recibir 403 (la generación no protege ningún recurso existente cuya fuga de existencia importe — mismo razonamiento que la creación de creative items en `011-creative-studio`).

#### Scenario: Rol no Creator rechazado
- **WHEN** un Content Reviewer o Visual Compliance Reviewer con membresía intenta generar
- **THEN** la respuesta es 403 y no se persiste ningún cambio

### Requirement: El brief de origen se conserva junto al borrador
El sistema SHALL persistir el brief que originó una generación junto a la versión resultante, distinto del `document` en sí. Un DRAFT producido por autoría manual (`PATCH /draft`) SHALL dejar este campo sin modificar: reemplazar el documento a mano no borra un brief de generación previo, y una versión nunca generada por IA simplemente no tiene brief.

#### Scenario: Brief disponible tras generar
- **WHEN** se consulta el DRAFT inmediatamente después de generarlo
- **THEN** el brief enviado está disponible junto al documento generado

#### Scenario: Edición manual no borra el brief previo
- **WHEN** un Creator edita manualmente (`PATCH /draft`) un DRAFT que fue generado previamente por IA
- **THEN** el documento se reemplaza según lo editado y el brief de la generación anterior permanece sin modificar
