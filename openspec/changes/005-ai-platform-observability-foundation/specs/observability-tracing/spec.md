## Purpose

Instrumenta los flujos de IA con un puerto de tracing desacoplado y asíncrono: implementación no-op segura por defecto y adapter Langfuse opcional controlado por entorno, con spans sanitizados que nunca capturan payloads crudos ni alteran estados de dominio.

## ADDED Requirements

### Requirement: Puerto de tracing con no-op por defecto
El módulo `observability` SHALL exponer un puerto de tracing asíncrono que las capabilities consumen por dependencia. Sin configuración de Langfuse, el sistema MUST usar una implementación no-op explícita que no lance errores ni realice llamadas de red; esta ausencia de configuración SHALL quedar observable (por ejemplo, un log único de tracing deshabilitado) sin exponer secretos.

#### Scenario: Arranque sin configuración
- **WHEN** la API inicia sin variables de entorno de Langfuse
- **THEN** las capabilities se instrumentan con el tracer no-op y la aplicación funciona sin errores de tracing

#### Scenario: Tests y desarrollo
- **WHEN** se ejecutan los tests de capabilities
- **THEN** el tracing es no-op y no genera llamadas de red ni errores

### Requirement: Adapter Langfuse opcional por entorno
El adapter de Langfuse SHALL activarse únicamente cuando las variables de entorno requeridas (`CONTENT_SUITE_LANGFUSE_PUBLIC_KEY`, `CONTENT_SUITE_LANGFUSE_SECRET_KEY`, `CONTENT_SUITE_LANGFUSE_HOST`) estén completas. Con configuración ausente el sistema SHALL usar el no-op con un log único; con configuración parcial SHALL usar también el no-op con un log único que identifique las variables faltantes por nombre, nunca por valor, sin lanzar errores ni realizar red. Su SDK SHALL importarse solo dentro del adapter de `observability`. La captura de input/output MUST estar deshabilitada: los spans no registran prompts crudos, respuestas crudas, tokens ni datos sensibles. Un fallo de inicialización del tracer (SDK ausente o roto, cliente no construible) MUST degradar a no-op con un log sanitizado; un error del tracer en runtime MUST degradarse sin romper la operación de dominio instrumentada.

#### Scenario: Configuración parcial
- **WHEN** solo algunas variables de entorno de Langfuse están configuradas
- **THEN** el sistema usa el tracer no-op y registra un único log que nombra las variables faltantes sin exponer ningún valor

#### Scenario: Fallo de inicialización
- **WHEN** la configuración está completa pero el SDK de Langfuse no puede inicializarse
- **THEN** el sistema degrada a no-op con un log sanitizado y la aplicación arranca sin errores de tracing

#### Scenario: Configuración presente
- **WHEN** las variables de entorno de Langfuse están completas
- **THEN** los spans se envían al tracer real sin capturar input/output crudos

#### Scenario: Fallo del tracer en runtime
- **WHEN** el tracer real falla durante una operación instrumentada
- **THEN** la operación de dominio completa normalmente y el fallo queda registrado de forma sanitizada

### Requirement: Metadatos de span estandarizados
Cada span de capability SHALL registrar entidad vinculada, `prompt_version`, modelo utilizado, latencia, un resumen estructurado acotado y error sanitizado cuando aplique. El resumen SHALL ser un contrato Pydantic con `extra="forbid"` y solo campos escalares del allowlist (`contract`, `ok`, `content_type`, `check_count`, `finding_count`), de modo que no pueda contener contenido crudo; el error sanitizado SHALL limitarse al nombre de la clase de excepción. El tracer MUST NOT cambiar estados de workflow ni persistir entidades de dominio; los IDs de trace se almacenarán solo cuando las entidades consumidoras existan.

#### Scenario: Span de una capability exitosa
- **WHEN** una capability completa una generación estructurada
- **THEN** el span registra entidad, prompt_version, modelo, latencia y el resumen acotado del resultado validado

#### Scenario: Span de una capability con error
- **WHEN** una capability falla por output malformado o proveedor ausente
- **THEN** el span registra el error sanitizado (nombre de clase) sin incluir payloads crudos ni secretos
