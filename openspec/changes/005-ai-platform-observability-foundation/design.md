## Context

Ver `proposal.md` y las specs de `ai-platform` y `observability-tracing`. La API ya tiene settings Pydantic con prefijo `CONTENT_SUITE_`, envelope de errores central y módulos `identity`, `brand_dna` y `health` con patrón router -> service -> policies/repository. No existen módulos `ai` ni `observability`; no hay SDKs de proveedor ni Langfuse instalados. `AI_SYSTEM.md` define las capabilities, contratos y prompt IDs que esta base debe soportar, y `specs/03-brand-knowledge-rag.md` en adelante los consumirán.

## Goals / Non-Goals

**Goals:**

- Fundamentos `ai` y `observability` reutilizables por Knowledge, Creative y Visual Audit sin decisiones de proveedor en el dominio.
- Contratos Pydantic con campos exactos + prompt registry + capability runner con DI, errores explícitos y fakes deterministas, todos asíncronos.
- Tracing no-op por defecto (configuración ausente o parcial); Langfuse solo con configuración completa y sin captura de input/output.
- Elección de bibliotecas verificada (Context7/registry) durante la implementación, no asumida aquí.

**Non-Goals:**

- No exponer endpoints de generación, ni generar contenido productivo, ni elegir proveedor/credenciales.
- No implementar retrieval/Knowledge, ni capabilities específicas de consumidor (las añaden sus changes).
- No añadir migraciones ni columnas de trace: cada spec consumidora añade sus columnas (`langfuse_trace_id` ya está previsto en `DATA_MODEL.md` para `creative_versions` y `visual_audits`).
- No mapear errores de proveedor a 503 en esta change: el envelope lo hará el boundary de API de cada consumidor.

## Decisions

### Estructura de módulos espejo del patrón existente

`apps/api/app/ai` con `contracts.py` (Pydantic), `ports.py` (Protocolos `TextModel`, `EmbeddingModel`, `VisionModel`), `prompts.py` (registry), `runner.py` (capability service), `errors.py` (`AIProviderNotConfiguredError`, `AIPromptNotFoundError`, `AIOutputValidationError`), `fakes.py` y `providers/` (adapters reales, únicos autorizados a importar SDKs). `apps/api/app/observability` con `ports.py` (`Tracer`), `noop.py`, `errors.py` y `langfuse_adapter.py`. Protocolos tipados en lugar de ABCs: sin herencia obligatoria, compatibles con fakes y con `ty`/ruff existentes.

Alternativa descartada: un único módulo `ai` con tracing embebido. Separa responsabilidades que `MODULES.md` distingue (AI Platform vs Observability) y permitiría tracing sin IA más adelante.

### Protocolos y runner asíncronos

Todas las operaciones de `ports.py` (`generate`, `generate_structured`, `analyze_structured`, `embed`), el puerto `Tracer`, el `runner.py` y los fakes son `async def`. Los SDKs de proveedor son bloqueantes o asíncronos según su propia API; el adapter es el único lugar donde se decide cómo envolverlos (p. ej. `asyncio.to_thread`), de modo que el dominio y los tests siempre esperan corutinas y ningún consumidor puede llamar a un adapter sin `await`. Los tests de puertos, runner, fakes y tracer usan `pytest.mark.asyncio` (o `anyio`), sin red.

Alternativa descartada: Protocolos síncronos con adapters que bloquean el event loop. Obligaría a cada router FastAPI a envolver llamadas en threads o degradaría el runtime.

### Orden de construcción: `observability` antes del runner

El tasks.md crea el puerto `Tracer` y su no-op (con resolución desde settings) en la sección 2, **antes** del runner (sección 4). Así el runner se integra con el tracer desde su primera versión (sección 4.1 incluye la emisión del span) y no existe un runner previo sin instrumentar que haya que reescribir.

Alternativa descartada: runner primero y "integrar tracer después". Duplicaría la tarea de instrumentación y dejaría una ventana con código de dominio sin trazabilidad.

### Representación de proveedor no configurado: adapter `None`

La resolución del adapter desde settings devuelve `TextModel | VisionModel | None` (lo mismo para los demás puertos). El runner recibe ese valor tal cual y lanza `AIProviderNotConfiguredError` al encontrar `None`, antes de resolver prompt o invocar el modelo, sin fallback. No existe un objeto adapter "tonto" que lance al invocarse: `None` es la única representación y el error sale del runner, un único punto para todos los consumidores.

Alternativa descartada: un adapter stub que lanza en cada método. Dos lugares donde puede surgir el error y obliga a distinguir stub de adapter real en tests.

### Capability runner como service compartido, no capabilities por consumidor

`runner.py` (async) ejecuta: validar adapter presente -> resolver prompt por ID (si no existe, `AIPromptNotFoundError` sin llamar al modelo) -> invocar `await TextModel.generate_structured` / `await VisionModel.analyze_structured` -> validar con el contrato Pydantic (`AIOutputValidationError` si falla) -> emitir span al `Tracer` (entidad, `prompt_version`, modelo, latencia, `TraceSummary`, error sanitizado) -> devolver output validado + metadatos. Los adapters y el tracer se reciben por parámetro/dependencia, nunca importados desde el dominio. La emisión del span se guarda: cualquier fallo del tracer se registra sanitizado y nunca rompe la operación de dominio (raíz única del guard: todos los consumidores pasan por el runner). Las capabilities específicas (creative generation, consistency, visual audit) serán wrappers delgados en sus changes, cuando existan sus inputs (contexto RAG, assets).

Alternativa descartada: implementar ya `generate_creative`/`check_consistency`/`audit_visual`. Sus inputs pertenecen a módulos que aún no existen; anticiparlos inventaría contratos de consumidor.

### Contratos Pydantic: campos exactos y `extra="forbid"`

Todos los contratos usan Pydantic v2 con `model_config = ConfigDict(extra="forbid")` y límites acotados. Definición canónica (única fuente; `contracts.py` y los tests la replican):

**`Finding` (compartido)** — requeridos, todos `str` acotados: `rule_id` (1–100), `category` (1–50), `expected` (1–500), `detected` (1–500), `evidence` (1–1000), `recommendation` (1–1000); enums: `severity: Literal["low","medium","high"]`, `status: Literal["pass","fail"]`.

**`Check`** — requeridos: `check_id` `str` (1–100), `label` `str` (1–200), `status: Literal["pass","fail"]`.

**`CreativeSection`** — requeridos: `heading` `str` (1–120), `body` `str` (1–10000).

**`CreativeOutput`** — requeridos: `content_type: Literal["product_description","video_script","image_prompt"]`, `title` `str` (1–200), `applied_rule_ids: list[str]` (máx 50, cada id 1–100, sin duplicados); opcionalidad excluyente: exactamente uno de `content: str | None` (1–10000) o `structured_sections: list[CreativeSection] | None` (máx 50); validador que rechaza ambos presentes o ambos ausentes.

**`ConsistencyResult`** — requeridos: `checks: list[Check]` (máx 100), `findings: list[Finding]` (máx 100), `summary: str` (1–2000).

**`VisualAuditResult`** — idéntico a `ConsistencyResult`.

El modelo backend calcula scores a partir de `findings`/`checks` (no hay threshold automático ni score emitido por el modelo).

Alternativa descartada: campos libres (`dict`) o `extra="ignore"`. Un output con campo extra pasaría silenciosamente y el contrato dejaría de describir el output real.

### `TraceSummary` acotado por allowlist

El resumen que viaja en el span es un contrato Pydantic propio con `extra="forbid"` y solo campos escalares: `contract: Literal["CreativeOutput","ConsistencyResult","VisualAuditResult"]`, `ok: bool`, `content_type: Literal["product_description","video_script","image_prompt"] | None` (solo para `CreativeOutput`), `check_count: int` (0–100), `finding_count: int` (0–100). No hay campos de texto libre, por diseño: es imposible que el span contenga prompts, respuestas crudas ni datos sensibles. El error sanitizado del span se restringe al nombre de la clase de excepción (`type(exc).__name__`), nunca `str(exc)` de un SDK externo.

Alternativa descartada: serializar el output validado completo en el span. `evidence`/`detected` de `Finding` son contenido del documento y no deben salir del backend.

### Errores explícitos internos, sin handler 503 aún

`AIProviderNotConfiguredError` se lanza al resolver un adapter sin configuración. No se registra handler en `errors.py` en esta change: ningún router actual puede lanzarla y el 503 con envelope corresponde al boundary de las changes consumidoras (decisión registrada en `API.md`: 503 cuando AI provider requerido no está disponible). La verificación de esta change invoca el runner internamente (test/script), no vía HTTP.

### Tracer no-op por defecto; estados de configuración Langfuse y fallos

`observability` resuelve el tracer desde settings con cuatro estados definidos sin ambigüedad:

1. **Configuración ausente** (ninguna var `CONTENT_SUITE_LANGFUSE_*`): `NoopTracer` + un único log info "tracing deshabilitado".
2. **Configuración parcial** (algunas vars): `NoopTracer` + un único log warning que nombra solo las variables faltantes (nombres, nunca valores), sin red ni excepción.
3. **Configuración completa** (`public_key`, `secret_key`, `host`): se construye el adapter Langfuse con import lazy del SDK dentro del adapter y captura de input/output deshabilitada.
4. **Fallo de inicialización con config completa** (SDK ausente/roto, credenciales rechazadas al construir el cliente): el adapter no se construye; se registra un log warning sanitizado (sin secretos) y se degrada a `NoopTracer`. La app arranca igual.

En runtime, el adapter Langfuse captura los fallos del SDK dentro de sí mismo y los registra sanitizados; además el runner guarda la emisión del span (ver decisión del runner). Ningún error del tracer rompe la operación de dominio ni cambia estados de workflow.

Alternativa descartada: inicializar Langfuse siempre y filtrar eventos. Acopla la app a la disponibilidad del SDK y arriesga envío accidental de payloads.

### Auditoría estática de imports

Verificación explícita (tarea 6.2): búsqueda estática en `apps/api/app` que garantiza que ningún SDK de proveedor de IA se importa fuera de `ai/providers/` y que `langfuse` solo se importa en `observability/langfuse_adapter.py`. Complementa la invariante de `AI_SYSTEM.md` y cierra la puerta a que un consumidor futuro importe un SDK directamente.

### Bibliotecas verificadas en la implementación

La elección concreta del SDK de Langfuse (y de cualquier SDK de proveedor futuro) NO se decide aquí: la tarea 5.1 exige verificar con Context7/documentación oficial la versión estable compatible con FastAPI/Pydantic v2 y Python 3.12 antes de `uv add`. Si la verificación cambia el enfoque del adapter, se documenta en la tarea sin tocar estas specs.

### Sin base de datos ni frontend

Ninguna migración. Los IDs de trace viven en memoria del span hasta que las entidades consumidoras persistan `langfuse_trace_id` en sus propias changes.

## Risks / Trade-offs

- [El runner anticipa mal las necesidades de consumidores] → mantenerlo mínimo (prompt + adapter + contrato + span); cada change consumidora puede evolucionarlo sin romper los Protocolos.
- [Langfuse SDK incompatible o cambia API] → verificación previa obligatoria y adapter aislado en `observability`; degradación documentada a no-op con log si el adapter no puede construirse (estado 4).
- [No-op puede ocultar que producción no traza] → log único por estado (1, 2 y 4) y test que verifica resolución explícita de tracer según settings.
- [Fakes desincronizados de interfaces reales] → fakes implementan los mismos Protocolos asíncronos y los tests de contratos corren contra ambos.

## Migration Plan

1. Additive: crear módulo `observability` (puerto + no-op + resolución), módulo `ai` (puertos, contratos, prompts, runner, fakes) y adapter Langfuse con sus tests; extender `config.py` con settings vacíos por defecto; `main.py` no cambia rutas.
2. Verificación: `uv run ruff check`, `uv run ty check`, `uv run pytest`, auditoría estática de imports y `openspec validate --strict`.
3. Rollback: eliminación de los módulos nuevos y de los settings añadidos; no hay datos ni contratos públicos que revertir.
