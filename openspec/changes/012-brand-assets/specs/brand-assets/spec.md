## Purpose

Gobierna el logo primario, el logo alternativo y la colección de referencias visuales de una marca: quién puede subirlos y leerlos, cómo se reemplazan los logos (slots únicos) frente a cómo se acumulan las referencias (colección), y cómo se apoyan en `private-storage` (008) para el almacenamiento real del archivo sin volver a especificar esa mecánica.

## ADDED Requirements

### Requirement: Logo primario y alternativo como slots únicos
El sistema SHALL mantener como máximo un asset `PRIMARY_LOGO` y como máximo un asset `ALT_LOGO` por marca. Subir un nuevo logo de un tipo que ya existe SHALL reemplazarlo: el objeto y la fila anteriores se eliminan y el nuevo se persiste en la misma operación — las dos versiones nunca coexisten de forma observable.

#### Scenario: Primer logo primario
- **WHEN** un Creator sube un archivo como `PRIMARY_LOGO` de una marca que aún no tiene uno
- **THEN** se crea el registro y queda como el único `PRIMARY_LOGO` de la marca

#### Scenario: Reemplazo de logo existente
- **WHEN** un Creator sube un nuevo archivo como `PRIMARY_LOGO` de una marca que ya tiene uno
- **THEN** el logo anterior (objeto y fila) se elimina y el nuevo queda como el único `PRIMARY_LOGO`, sin que ambos coexistan en ningún momento observable por un cliente

### Requirement: Colección de referencias visuales
El sistema SHALL permitir múltiples assets `VISUAL_REFERENCE` por marca sin reemplazo implícito: cada subida agrega un asset nuevo a la colección. Cada referencia SHALL poder eliminarse individualmente sin afectar al resto de la colección ni a los logos.

#### Scenario: Múltiples referencias coexisten
- **WHEN** un Creator sube varias imágenes como `VISUAL_REFERENCE` de la misma marca
- **THEN** todas coexisten como assets independientes y se listan juntas

#### Scenario: Eliminación individual
- **WHEN** un Creator elimina una referencia visual específica
- **THEN** esa fila y su objeto desaparecen sin afectar a las demás referencias ni a los logos

### Requirement: Lectura por cualquier miembro de la marca
El sistema SHALL permitir a cualquier miembro de la marca (`CREATOR`, `CONTENT_REVIEWER`, `VISUAL_REVIEWER`) listar los brand assets de sus marcas, cada uno con una signed URL vigente. Listar sin membresía en la marca indicada responde 403. El Visual Compliance Reviewer SHALL poder leer el logo primario de una marca como contexto de comparación al auditar un visual de esa marca — consumo directo desde `visual-compliance`.

#### Scenario: Lectura por cualquier rol con membresía
- **WHEN** un `CONTENT_REVIEWER` o `VISUAL_REVIEWER` con membresía lista los assets de su marca
- **THEN** recibe el listado completo con signed URLs vigentes, sin necesitar rol `CREATOR`

#### Scenario: Listado sin membresía
- **WHEN** un usuario sin membresía en la marca solicita su listado de assets
- **THEN** la respuesta es 403 y no se emite ninguna signed URL

### Requirement: Escritura restringida a Creator con membresía
Subir un logo, subir una referencia visual y eliminar cualquier asset SHALL exigir rol `CREATOR`. Un miembro con rol `CONTENT_REVIEWER` o `VISUAL_REVIEWER` MUST recibir 403 al intentar cualquiera de estas acciones. Subir no protege ninguna fuga de existencia (no hay un asset previo que ocultar): un actor sin membresía en la marca del path MUST recibir 403. Eliminar sí protege un recurso existente: un asset inexistente, un asset que pertenece a otra marca, o un actor sin membresía en la marca del asset MUST responder 404 en los tres casos, indistinguibles entre sí.

#### Scenario: Revisor no puede escribir
- **WHEN** un `CONTENT_REVIEWER` o `VISUAL_REVIEWER` con membresía intenta subir o eliminar un asset
- **THEN** la respuesta es 403 y no se persiste ni elimina nada

#### Scenario: Subida sin membresía
- **WHEN** un usuario sin membresía en la marca del path intenta subir un asset
- **THEN** la respuesta es 403

#### Scenario: Eliminación de asset ajeno o inexistente
- **WHEN** se intenta eliminar un asset que no existe, que pertenece a otra marca, o de una marca sin membresía del actor
- **THEN** la respuesta es 404 en los tres casos

### Requirement: Almacenamiento vía private-storage (referencia, no reespecificación)
La subida y lectura de brand assets SHALL apoyarse en la capability `private-storage` (008-visual-compliance): validación server-side del archivo real por contenido (no solo por content-type declarado), tamaño dentro del máximo configurado, tipo restringido a imágenes permitidas, ruta de storage derivada server-side (el cliente MUST NOT elegir ni enviar el path), y lectura exclusivamente vía signed URLs de corta duración. `brand-assets` MUST NOT reimplementar esta mecánica ni exponer el path interno de storage en ninguna respuesta: reutiliza el mismo puerto que `private-storage` ya especifica ("Storage privado por defecto", "Validación server-side de archivo", "Signed URLs de corta duración", "Backend de storage aislado y reemplazable").

#### Scenario: Archivo inválido rechazado
- **WHEN** se sube un archivo cuyo contenido real no es una imagen de un tipo permitido, o excede el tamaño máximo configurado
- **THEN** la subida se rechaza (422) y no se crea fila ni queda objeto huérfano en storage

#### Scenario: Solo signed URLs en las respuestas
- **WHEN** se lista o se consulta un brand asset
- **THEN** la respuesta incluye una signed URL vigente y nunca el path interno de storage

### Requirement: Vínculo con la versión de Brand DNA activa al momento de la subida
Cada brand asset SHALL capturar, al crearse, el id de la versión de Brand DNA `ACTIVE` de la marca en ese momento (nulo si la marca aún no tiene ninguna publicada) — el mismo patrón de snapshot que ya usan `creative_versions`. El vínculo es solo de referencia/auditoría: el asset SHALL seguir siendo válido y legible aunque la marca publique versiones de Brand DNA posteriores; no se actualiza retroactivamente.

#### Scenario: Snapshot al momento de subida
- **WHEN** se sube un asset mientras la marca tiene una versión de Brand DNA `ACTIVE`
- **THEN** el asset persiste esa versión como referencia y la conserva aunque después se publique una versión nueva

#### Scenario: Sin Brand DNA publicada
- **WHEN** se sube un asset y la marca aún no tiene ninguna versión de Brand DNA `ACTIVE`
- **THEN** el asset se crea con esa referencia nula
