# observability-facade — Delta Spec

## Purpose

Exponer una facade de lectura segura sobre traces ya emitidos: listado y detalle autorizados por brand y entidad, con metadatos sanitizados allowlist, estados explícitos y UI in-app. La facade nunca reemplaza a Langfuse como almacén de telemetría ni permite invocar proveedores.

## ADDED Requirements

### Requirement: Endpoints facade de traces
El sistema SHALL exponer `GET /api/v1/traces` y `GET /api/v1/traces/{trace_id}` bajo `/api/v1` con JWT Bearer. El listado SHALL soportar paginación (`limit` con máximo acotado y `offset`) y filtros allowlist: `brand_id`, `entity_type`, `entity_id` y rango de fechas (`from`/`to`). Cualquier parámetro fuera del allowlist SHALL ignorarse. Los errores SHALL usar el envelope de respuesta existente: 403 para falta de permiso, 404 para trace inexistente o no autorizado, 422 para parámetros inválidos.

#### Scenario: Listado paginado de una marca autorizada
- **WHEN** un usuario con membresía en la marca B solicita `GET /api/v1/traces?brand_id=B&limit=20`
- **THEN** recibe hasta 20 traces sanitizadas de la marca B con su token de paginación y metadatos allowlist

#### Scenario: Filtro fuera del allowlist
- **WHEN** la solicitud incluye un parámetro no permitido (por ejemplo `prompt=`)
- **THEN** el parámetro se ignora y la respuesta se comporta como sin él

#### Scenario: Trace inexistente o ajena
- **WHEN** un usuario solicita el detalle de un `trace_id` inexistente o de una marca sin membresía
- **THEN** recibe 404 o 403 con el envelope de errores, sin filtrar información sobre otras marcas

### Requirement: Autorización por membresía en backend
El backend SHALL resolver la membresía del usuario autenticado antes de consultar cualquier trace y SHALL filtrar por los brands autorizados. El sistema MUST NOT aceptar `brand_id` ni role del frontend como autoridad: el role efectivo proviene de `brand_memberships`. Un usuario SHALL ver únicamente traces de sus marcas y entidades autorizadas.

#### Scenario: Usuario sin membresía
- **WHEN** un usuario autenticado sin membresía en la marca B lista traces con `brand_id=B`
- **THEN** recibe 403 y no se consulta ningún trace de esa marca

#### Scenario: Trace sin binding de marca
- **WHEN** existe en el read model un trace sin `brand_id` asociado
- **THEN** ese trace no aparece en ningún listado ni es accesible por detalle

### Requirement: Sanitización de payloads
Tanto el listado como el detalle SHALL exponer únicamente metadatos allowlist: capability u operación, prompt version, modelo, referencia de entidad (`entity_type`/`entity_id`), brand, duración, outcome (éxito/error con tipo de error sanitizado) y timestamps. El sistema MUST NOT exponer secretos, tokens, prompts completos, respuestas crudas, chain-of-thought ni payloads de proveedor.

#### Scenario: Detalle sanitizado
- **WHEN** un usuario autorizado abre el detalle de un trace
- **THEN** ve solo los metadatos allowlist y ningún campo de texto libre de contenido generado o capturado

### Requirement: Read model local mínimo
El sistema SHALL mantener un read model local (`observability_trace_index`) con una fila sanitizada por span emitido, escrita en el punto de emisión y sin bloquear ni romper la operación de dominio si la escritura falla. El read model SHALL registrar `trace_id` (nullable cuando el tracer activo no lo provee), `brand_id` nullable, `entity_type`, `entity_id` nullable, `operation`, `prompt_version`, modelo, latencia, outcome, error sanitizado y timestamps. El read model MUST NOT duplicar la telemetría completa de Langfuse ni almacenar contenido crudo.

#### Scenario: Escritura con tracer no-op
- **WHEN** se emite un span con el tracer no-op (sin Langfuse configurado)
- **THEN** el read model persiste la fila sanitizada con `trace_id` nulo y la operación de dominio continúa sin errores

#### Scenario: Fallo de escritura del read model
- **WHEN** la persistencia del read model falla durante una emisión
- **THEN** la operación de dominio que originó el span completa normalmente y el fallo queda registrado de forma sanitizada

### Requirement: Estado explícito sin Langfuse
Cuando Langfuse no está configurado, la facade SHALL exponer ese estado de forma explícita (indicador en la respuesta del listado y en la UI) y el sistema SHALL seguir operando: los flujos de dominio no se rompen y las capabilities no fallan por tracing. La facade SHALL emitir telemetría mínima de sus propias lecturas, sin recursión (sus lecturas no se indexan a sí mismas) y sin logging de secretos.

#### Scenario: Langfuse ausente
- **WHEN** las variables de Langfuse no están configuradas y un usuario lista traces
- **THEN** la respuesta indica explícitamente el estado sin Langfuse y devuelve las filas locales disponibles

#### Scenario: Sin recursión
- **WHEN** la facade sirve lecturas
- **THEN** esas lecturas no generan nuevas filas en el read model

### Requirement: UI de Observability
La aplicación web SHALL mostrar la pantalla Observability activada para los roles definidos por contrato (Creator, Content Reviewer y Visual Reviewer, con alcance limitado a sus marcas). La pantalla SHALL ofrecer filtros mínimos (marca, tipo de entidad, fecha), estados de carga, error y vacío diferenciados, y un detalle sanitizado coherente con el allowlist del API. La UI SHALL mostrar el estado sin Langfuse cuando aplique y nunca SHALL renderizar datos ficticios como actividad real.

#### Scenario: Estados diferenciados
- **WHEN** la pantalla carga, falla o no tiene datos
- **THEN** muestra el estado de carga, el mensaje de error con reintento o el estado vacío explícito, respectivamente

#### Scenario: Filtro por marca propia
- **WHEN** un usuario con varias membresías filtra por una de sus marcas
- **THEN** la lista muestra solo traces de esa marca, obtenidas del backend autorizado

### Requirement: Binding con entidades de dominio
El contexto de emisión y el read model SHALL soportar referencias genéricas de entidad (`entity_type` + `entity_id`) que enlazan traces con versiones de Brand DNA, Creative y Visual Audit (valores `brand_dna_version`, `creative_version`, `visual_audit`) cuando existan. Las changes consumidoras futuras SHALL poblar estas referencias vía el contexto de emisión; la facade las devuelve como metadatos de solo lectura y permiten filtrar el listado por entidad.

#### Scenario: Trace de una versión futura de creative
- **WHEN** una capability se emite con contexto `entity_type=creative_version` y su `entity_id`
- **THEN** la fila del read model queda enlazada y la facade la expone en listado y detalle
