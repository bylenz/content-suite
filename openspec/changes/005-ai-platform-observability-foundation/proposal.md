## Why

Knowledge, Creative y Visual Audit (próximas changes) necesitan consumir IA y trazabilidad sin acoplar el dominio a SDKs de proveedor. Hoy no existen los módulos `ai` ni `observability`, ni contratos estructurados, ni prompt registry, ni tracing: sin esta base, cada consumidor improvisaría su propio patrón y el repositorio perdería la invariante "providers no se importan fuera de adapters".

## What Changes

- Crear el módulo interno `apps/api/app/ai` con interfaces provider-agnostic **asíncronas** (`TextModel`, `EmbeddingModel`, `VisionModel`; todas las operaciones `async def`) y contratos Pydantic con campos y enums exactos y `extra="forbid"` para output creativo, consistencia y visual audit; sin persistir chain-of-thought.
- Crear el prompt registry versionado con los IDs iniciales (`brand.architect.v1`, `creative.product_description.v1`, `creative.video_script.v1`, `creative.image_prompt.v1`, `consistency.text.v1`, `audit.visual.v1`) y un capability service **asíncrono** que recibe adapters por dependencia (un adapter `None` es la única representación de proveedor no configurado y produce error explícito sin fallback), valida el output contra su contrato y emite span al tracer.
- Crear el módulo interno `apps/api/app/observability` **antes del runner** con un puerto de tracing asíncrono (`Tracer`), implementación no-op por defecto para desarrollo/test que distingue configuración de Langfuse ausente, parcial y completa, y adapter Langfuse opcional habilitado solo con configuración completa, con captura de input/output deshabilitada y degradación sanitizada ante fallos de inicialización y de runtime.
- Añadir fakes deterministas asíncronos para tests, una auditoría estática de imports (SDKs de proveedor solo en `ai/providers/`; Langfuse solo en su adapter) y verificación de bibliotecas (SDK de Langfuse) como decisión de implementación validada con Context7/documentación oficial antes de instalar.

## Capabilities

### New Capabilities
- `ai-platform`: interfaces de modelo asíncronas, contratos estructurados con campos exactos, prompt registry versionado y ejecución de capabilities con adapters inyectados y errores explícitos de proveedor ausente.
- `observability-tracing`: puerto de tracing asíncrono con no-op seguro por defecto (configuración ausente o parcial) y adapter Langfuse opcional con metadatos de span acotados por allowlist y sin captura de payloads crudos.

### Modified Capabilities
- Ninguna.

## Impact

- Afecta `apps/api` (nuevos módulos `ai` y `observability`, `config.py` para settings de proveedor/Langfuse, tests nuevos).
- Puede añadir dependencias Python vía `uv` (SDK de Langfuse opcional) solo tras verificación documentada; actualiza `pyproject.toml` y `uv.lock`.
- No añade endpoints públicos, no cambia migraciones, base de datos, frontend, workflows ni contratos API existentes. El 503 por proveedor/contexto ausente se definirá en el boundary de API de las changes consumidoras; en esta change el error se verifica invocando el runner internamente, no vía HTTP.
