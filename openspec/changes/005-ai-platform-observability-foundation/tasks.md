## 1. Módulo `ai`: puertos, errores y configuración

- [x] 1.1 Crear `apps/api/app/ai` con `ports.py` (Protocolos asíncronos `TextModel`, `EmbeddingModel`, `VisionModel` con `generate`, `generate_structured`, `analyze_structured`, `embed` como `async def`) y `errors.py` (`AIProviderNotConfiguredError`, `AIPromptNotFoundError`, `AIOutputValidationError`); verificar con `uv run ty check` y un test que instancia un fake asíncrono por cada puerto.
- [x] 1.2 Extender `config.py` con settings vacíos por defecto para proveedor y Langfuse (prefijo `CONTENT_SUITE_`, ej. `ai_provider`, `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host`); verificar que la app inicia sin configuración y que settings ausentes no lanzan errores (test de Settings).

## 2. Módulo `observability`: puerto de tracing y no-op (antes del runner)

- [x] 2.1 Crear `apps/api/app/observability` con `ports.py` (Protocolo asíncrono `Tracer` con span por capability y `TraceSummary` acotado según `design.md`), `noop.py` y resolución desde settings que distingue configuración de Langfuse ausente, parcial y completa; verificar con tests que: sin configuración o parcial se usa el no-op con un único log (que nombra variables faltantes pero nunca sus valores), no hay red, y que la resolución es explícita según settings.

## 3. Módulo `ai`: contratos y prompt registry

- [x] 3.1 Crear `contracts.py` con `CreativeOutput`, `ConsistencyResult`, `VisualAuditResult`, `Finding` y `TraceSummary` con los campos, tipos, enums, opcionalidad, límites y `extra="forbid"` exactos definidos en `design.md`; verificar con tests que aceptan ejemplos válidos y rechazan outputs malformados por campo requerido, tipo, valor de enum, campo extra y por incumplir la exclusión mutua `content`/`structured_sections`.
- [x] 3.2 Crear `prompts.py` con el registry inmutable de los seis IDs iniciales (`brand.architect.v1`, `creative.product_description.v1`, `creative.video_script.v1`, `creative.image_prompt.v1`, `consistency.text.v1`, `audit.visual.v1`); verificar con tests que un ID inexistente lanza `AIPromptNotFoundError` sin llamar al modelo.

## 4. Módulo `ai`: runner y fakes (requiere el `Tracer` de 2.1)

- [x] 4.1 Crear `runner.py` asíncrono (capability service: validar adapter presente -> resolver prompt -> llamar adapter con `await` -> validar output con el contrato Pydantic -> emitir span al `Tracer` -> devolver output validado + metadatos con `prompt_version` y modelo) recibiendo adapter (`TextModel | VisionModel | None`) y tracer por dependencia; el adapter `None` es la única representación de proveedor no configurado y MUST lanzar `AIProviderNotConfiguredError` sin fallback; verificar con tests que: un output malformado lanza `AIOutputValidationError`; el span de éxito y de error registran solo `TraceSummary` y error sanitizado (nombre de clase de excepción); un fallo del tracer nunca rompe la operación de dominio.
- [x] 4.2 Crear `fakes.py` con fakes asíncronos deterministas de `TextModel`, `EmbeddingModel` y `VisionModel`; verificar con tests (happy path + output malformado + proveedor ausente) que todo corre sin llamadas de red.

## 5. Adapter Langfuse (opcional, env-gated)

- [x] 5.1 Verificar con Context7/documentación oficial el SDK de Langfuse (versión estable compatible con Python 3.12 y Pydantic v2) y documentar la decisión en la tarea antes de instalar con `uv add`; si la verificación invalida el enfoque del adapter, registrar el hallazgo y el ajuste en esta misma tarea.
  - Decisión: Context7 (`/langfuse/langfuse-python`) reporta SDK v4.14.x soportando Python 3.10–3.12 con cliente Pydantic v2; `uv add langfuse` resolvió **4.15.2** (compatible con `requires-python >=3.12`). Verificado en el entorno: `Langfuse.start_observation(name=..., as_type='span')` existe y su `input`/`output` por defecto son `None`; el constructor acepta `public_key`/`secret_key`/`host`. Captura deshabilitada por construcción: el adapter nunca pasa `input`/`output` y los metadatos solo llevan escalares + `TraceSummary`. Enfoque del adapter validado, sin ajustes.
- [x] 5.2 Implementar `langfuse_adapter.py` con import lazy del SDK solo dentro del adapter, activado únicamente con configuración completa de `CONTENT_SUITE_LANGFUSE_*` (ausente y parcial ya resuelven a no-op en 2.1); fallo de inicialización degrada a no-op con log sanitizado y fallo en runtime se captura dentro del adapter sin romper la operación; verificar con tests usando un stub del SDK (sin red) que: sin config -> no-op, parcial -> no-op, con config -> adapter, fallo de init -> no-op + log, fallo en runtime -> la operación de dominio completa.

## 6. Verificación

- [x] 6.1 Ejecutar `uv run ruff check`, `uv run ty check` y `uv run pytest` en `apps/api`; confirmar cero llamadas de red en tests (fakes/stubs) y que no cambian migraciones, endpoints, frontend ni handlers de `errors.py`.
  - Resultado: ruff `All checks passed!`; ty `All checks passed!`; pytest **125 passed** (2 warnings preexistentes de starlette/httpx, ajenos a esta change). Cero red: capabilities usan `Fake*Model` y el SDK Langfuse solo vía stubs inyectados. `git status` confirma que `alembic/`, routers, frontend y `app/errors.py` no cambian.
- [x] 6.2 Auditoría estática de imports en `apps/api/app`: ningún SDK de proveedor de IA se importa fuera de `ai/providers/` y `langfuse` solo se importa en `observability/langfuse_adapter.py`; documentar el comando ejecutado y su salida en esta tarea.
  - Test durable: `tests/test_import_audit.py` (AST, detecta `import`/`from` con alias) — passed.
  - Comando manual: `grep -rnE "^[[:space:]]*(import|from)[[:space:]]+(langfuse|openai|anthropic|google)" app --include='*.py' | grep -v 'app/observability/langfuse_adapter.py' | grep -v 'app/ai/providers/'` → salida vacía (exit 1 del último grep = sin violaciones). `ai/providers/` aún no contiene adapters reales.
- [x] 6.3 Con variables de proveedor/Langfuse ausentes, iniciar la API y confirmar arranque sin errores de tracing; invocar el runner internamente (test/script de integración, sin endpoint público) confirmando error controlado `AIProviderNotConfiguredError` y ausencia de secretos en logs; documentar el resultado en esta tarea.
  - Resultado (`tests/test_ai_startup_integration.py`, passed): la app arranca y sirve `/health/live`; `resolve_tracer` resuelve no-op; la invocación interna del runner con adapter `None` lanza `AIProviderNotConfiguredError` (sin fallback) y ningún log contiene el payload ni secretos.
- [x] 6.4 Ejecutar `npx @fission-ai/openspec@latest validate 005-ai-platform-observability-foundation --strict` y `git diff --check`; dejar la change sin archivar.
  - Resultado: `Change '005-ai-platform-observability-foundation' is valid`; `git diff --check` limpio; nada en staging; change sin archivar.
