## Purpose

Guarda los visuales del producto en storage privado con validación server-side de archivo y entrega acceso temporal vía signed URLs: ningún objeto es público por defecto y ninguna ruta de storage se expone al frontend como dirección de lectura.

## ADDED Requirements

### Requirement: Storage privado por defecto
El sistema SHALL almacenar cada visual en un bucket privado: ningún objeto SHALL ser legible públicamente por defecto y el sistema MUST NOT exponer operaciones que conviertan objetos en públicos. La única vía de lectura SHALL ser una signed URL de corta duración emitida tras autorización backend. La organización de rutas SHALL derivarse server-side de la marca y del recurso (creative item y versión de visual): el cliente MUST NOT elegir ni enviar el path de storage. El stop condition de la spec 06 aplica: si un objeto se hace público por defecto, la change se detiene.

#### Scenario: Objeto no accesible públicamente
- **WHEN** se sube un visual y se intenta resolver su ruta sin credenciales
- **THEN** el objeto no es accesible y no existe ninguna URL pública asociada

#### Scenario: El cliente no controla el path
- **WHEN** un Creator sube un visual indicando solo el archivo
- **THEN** el backend determina la ruta a partir de marca, creative item y versión, y la petición que envía un path arbitrario no altera la ubicación real

### Requirement: Validación server-side de archivo
El sistema SHALL validar cada archivo en el backend antes de persistirlo o exponerlo: tipo real verificado por contenido (magic bytes) y no solo por el content type declarado, tamaño dentro del límite máximo configurado y tipo permitido restringido a imágenes. Un archivo que no pase la validación SHALL ser rechazado con error 422 de validación antes de crear cualquier registro de visual asset, y no SHALL dejarse huérfano en storage.

#### Scenario: Content type falsificado
- **WHEN** se sube un archivo declarado como imagen cuyo contenido real no corresponde a un tipo permitido
- **THEN** la subida se rechaza con 422 y no se persiste ningún objeto ni registro

#### Scenario: Tamaño fuera de límite
- **WHEN** se sube un archivo mayor que el máximo configurado
- **THEN** la subida se rechaza con 422 antes de transferir el objeto a storage

#### Scenario: Sin registros huérfanos
- **WHEN** la validación de archivo falla después de haberse intentado el upload
- **THEN** no queda ningún objeto persistido en storage ni fila de visual asset creada

### Requirement: Signed URLs de corta duración
El sistema SHALL emitir signed URLs con expiración corta configurada, solo para usuarios autorizados sobre recursos de su marca, tras validar el recurso solicitado. Una signed URL vencida MUST NOT seguir resolviendo el objeto, y el sistema MUST NOT devolver rutas de storage internas en ninguna respuesta API: el frontend solo recibe signed URLs.

#### Scenario: URL autorizada con expiración corta
- **WHEN** un Visual Compliance Reviewer abre el detalle de un visual de su marca
- **THEN** recibe una signed URL con expiración corta que resuelve el objeto mientras es vigente

#### Scenario: Sin membresía no hay URL
- **WHEN** un usuario autenticado sin membresía en la marca solicita el visual
- **THEN** la respuesta es 403 y no se emite ninguna signed URL, exista o no el recurso

#### Scenario: Sin rutas internas en respuestas
- **WHEN** cualquier endpoint devuelve datos de un visual asset
- **THEN** la respuesta contiene una signed URL temporal y nunca el path interno de storage

### Requirement: Backend de storage aislado y reemplazable
El acceso a storage SHALL ocurrir exclusivamente a través de un puerto inyectado en los services de dominio; el SDK del proveedor MUST importarse solo dentro del adapter del módulo storage, nunca en routers ni services de dominio. Un resolver env-gated SHALL construir el adapter solo con configuración completa; configuración ausente o parcial resuelve a adapter no disponible y las operaciones que lo requieren fallan con 503 controlado, sin objetos falsos ni fallback silencioso. Los tests SHALL usar un fake determinista del puerto.

#### Scenario: SDK aislado en el adapter
- **WHEN** se auditan estáticamente los imports de `apps/api/app`
- **THEN** el SDK de storage solo aparece dentro del módulo storage y ningún router o service de dominio lo importa

#### Scenario: Storage no configurado
- **WHEN** se intenta subir o firmar un visual sin configuración completa del backend de storage
- **THEN** la operación responde 503 con envelope, sin crear registros ni objetos parciales

#### Scenario: Tests sin red
- **WHEN** la suite de tests ejercita upload, validación y signed URLs
- **THEN** lo hace contra un fake determinista del puerto, sin llamadas de red ni credenciales reales
