# Content Suite

Plataforma AI-first para mantener la consistencia de marca en lanzamientos masivos de productos: un Manual de Marca generado por IA se convierte en conocimiento recuperable (RAG), cada pieza de contenido se genera respetándolo, pasa por un flujo de aprobación con dos revisores humanos y una auditoría visual multimodal, y todo queda trazado en Langfuse.

Respuesta al **Reto Técnico: Content Suite** (Alicorp IAGen).

## Entrega

| Entregable | Valor |
| --- | --- |
| Aplicación web | https://content-suite-web.vercel.app/ |
| API (FastAPI) | https://content-suite-api-iy88.onrender.com (`/health/ready`, `/docs`) |
| Repositorio | https://github.com/bylenz/content-suite |
| Dependencias Python | `apps/api/requirements.txt` (exportado desde `uv.lock`; `pyproject.toml` + `uv.lock` son la fuente) |
| Langfuse | _URL del proyecto entregada junto con las credenciales_ |
| Credenciales (3 roles) | _Entregadas por separado a los evaluadores; ver [Roles y credenciales](#roles-y-credenciales)_ |
| Presentación ejecutiva | 6 diapositivas: arquitectura, valor de negocio y limitaciones (entregada junto con las credenciales) |

> La API corre en el plan gratuito de Render: tras ~15 minutos sin tráfico se suspende y la primera petición puede tardar 30–60 s. El frontend muestra el estado de conexión mientras despierta.

## Cómo cubre los módulos del reto

| Módulo del reto | Implementación en Content Suite |
| --- | --- |
| **I. Brand DNA Architect** | `POST /brand-dna/generate` recibe un brief (producto, tono, público) y la IA devuelve un manual estructurado (Pydantic `BrandDNAOutput`: brand core, audiencia, tono, mensajes, reglas, guías visuales). El Creator lo edita como borrador y lo **publica como versión inmutable**. Al publicar, el módulo Knowledge lo trocea, genera embeddings y lo guarda en **pgvector** (`brand_knowledge_chunks`). |
| **II. Creative Engine** | Creative Studio crea **descripciones de producto, guiones de video y prompts de imagen**. Antes de cualquier generación el backend construye un **contexto híbrido**: reglas obligatorias (always/never/restricciones) filtradas por metadata + top-k semántico por tipo de tarea. Si no hay Brand Knowledge sincronizado, no genera contenido genérico: responde 503 controlado. Cada versión guarda las reglas aplicadas (`applied_rule_ids`, verificadas contra lo recuperado) y un **consistency check** contra el manual. |
| **III. Governance & Multimodal Audit** | Flujo de estados `DRAFT → PENDING_CONTENT_REVIEW → CONTENT_CHANGES_REQUESTED / CONTENT_APPROVED → PENDING_VISUAL_REVIEW → VISUAL_CHANGES_REQUESTED / FINAL_APPROVED`. El **Content Reviewer (Aprobador A)** aprueba o pide cambios sobre la versión exacta enviada. El **Visual Compliance Reviewer (Aprobador B)** recibe la imagen subida y ejecuta la auditoría: un modelo de visión contrasta el visual con las reglas visuales recuperadas del manual y devuelve `checks` pass/fail por regla, `findings` con evidencia y recomendación, y un score determinista calculado en backend. La decisión final es humana. |
| **IV. Observabilidad** | Cada capability de IA (generación de Brand DNA, sync de knowledge, generación creativa, consistency check, auditoría visual) emite spans a **Langfuse** con el contexto recuperado (`retrieved_rule_ids`), `prompt_version`, modelo, latencia y estado. El `langfuse_trace_id` se persiste en versiones y auditorías, y la app expone una vista **Observability** (`GET /api/v1/traces`) como facade de solo lectura. |

Criterios de evaluación: prompts versionados en `apps/api/app/ai/prompts.py` (`brand.architect.v1`, `creative.*.v1`, `consistency.text.v1`, `audit.visual.v1`); RBAC y transiciones de estado aplicadas en backend (`*/policies.py`, 403/409); RAG híbrido en `apps/api/app/knowledge/`; front, API y modelos integrados con adaptadores intercambiables en `apps/api/app/ai/providers/`.

## Roles y credenciales

Los tres roles del reto se mapean así (el rol lo resuelve el backend en `GET /api/v1/me` a partir de `brand_memberships`; la UI solo oculta controles):

| Rol del reto | Rol en la app | Ve en el sidebar | Puede |
| --- | --- | --- | --- |
| Creador | `CREATOR` | Dashboard, Brand DNA, Creative Studio, Observability | Crear/generar/publicar Brand DNA, subir logo y referencias, crear ítems, generar, regenerar, editar como nueva versión, consistency check, subir visual, enviar a revisión. No aprueba. |
| Aprobador A | `CONTENT_REVIEWER` | Dashboard, Brand DNA (lectura), Approvals, Observability | Ver cola, inspeccionar versión enviada y contexto aplicado, aprobar o solicitar cambios. Nunca edita contenido. |
| Aprobador B | `VISUAL_REVIEWER` | Dashboard, Brand DNA (lectura), Brand Audit, Observability | Ver cola visual, ejecutar auditoría multimodal, aprobar o solicitar cambios sobre el visual (con aceptación explícita de excepciones HIGH). |

Las credenciales (correo + contraseña de Supabase Auth para cada rol, todas con membresía en la marca demo **Kinu**) no se versionan en el repositorio; se entregan junto con la URL de Langfuse.

## Recorrido sugerido para evaluar

1. **Creator** → *Brand DNA* → *Generar con IA*: brief tipo "Snack saludable de quinua, tono divertido pero profesional, público Gen Z". Revisar el borrador y **Publicar**. En *Brand DNA* se ve el estado de sincronización del Brand Knowledge (chunks indexados en pgvector).
2. **Creator** → *Creative Studio* → nuevo ítem (descripción, guion o prompt de imagen) → **Generar**. Abrir *Contexto aplicado* para ver qué reglas obligatorias y semánticas se recuperaron. Ejecutar **Consistency check**, subir el visual del producto y **Enviar a revisión**.
3. **Aprobador A** → *Approvals*: inspeccionar la versión exacta enviada, **Solicitar cambios** (con feedback) o **Aprobar**.
4. **Aprobador B** → *Brand Audit*: **Ejecutar auditoría** sobre la imagen; el resultado muestra check verde por regla o el hallazgo con evidencia (p. ej. logo fuera de las reglas de uso), score y resumen. **Aprobar** o **Solicitar cambios**.
5. Cualquier rol → *Observability*: cada operación de IA con su `trace_id`, modelo, latencia y reglas recuperadas; el mismo `trace_id` se busca en Langfuse para ver el prompt completo.

## Arquitectura

```text
Brand Brief → Brand DNA (versionado) → Brand Knowledge (pgvector)
           → Creative generation (RAG híbrido) → Content Review (humano)
           → Visual upload → Multimodal Audit (visión + RAG) → Visual decision (humano)
           ↘ Langfuse traces en cada capability de IA
```

- **Monorepo** con npm workspaces + Turborepo: `apps/web` (React SPA) y `apps/api` (FastAPI).
- `apps/api` es un **monolito modular**: `identity` (RBAC), `brand_dna`, `brand_assets`, `knowledge` (RAG), `creative`, `governance`, `visual_audit`, `activity`, `observability`, `ai` (plataforma de IA), `storage`. Cada módulo tiene `router / service / repository / policies / schemas / models`.
- **PostgreSQL (Supabase)** es el estado canónico; **pgvector** guarda una representación derivada del Brand DNA publicado (nunca es fuente de verdad). En local se usa SQLite con la misma migración Alembic y un ranking coseno en Python como seam de pruebas.
- **RAG híbrido** (ADR-004): reglas obligatorias por metadata + búsqueda semántica top-k por tarea (texto, prompt de imagen, auditoría visual). Fail-safe: sin conocimiento obligatorio no se genera.
- **Plataforma de IA** (ADR-005): los dominios consumen puertos `TextModel`, `VisionModel`, `EmbeddingModel`; los SDKs solo viven en `app/ai/providers/`. Fakes deterministas para tests.
- **Auth**: Supabase Auth (correo + contraseña) en el front; la API verifica el JWT (issuer + audiencia) y resuelve rol y membresía desde la base de datos. RLS endurecido en Supabase (change 007).
- **Storage**: bucket privado de Supabase Storage para visuales y assets de marca; solo URLs firmadas de corta duración (300 s) y límite de 5 MB por archivo.

Documentación de diseño: `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `MODULES.md`, `DATA_MODEL.md`, `WORKFLOWS.md`, `AI_SYSTEM.md`, `API.md`, `docs/adr/*`, `docs/OBSERVABILITY.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/UI_UX.md`.

## Stack

| Capa | Tecnología |
| --- | --- |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS 4, TanStack Query, React Router, React Hook Form + Zod, shadcn/ui primitives, motion; desplegado en **Vercel** |
| Backend | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, `uv`; desplegado en **Render** (`render.yaml`) |
| Datos / Auth / Storage | **Supabase**: PostgreSQL + pgvector, Auth, Storage privado |
| Texto y embeddings | **OpenAI** (`gpt-4o-mini`, `text-embedding-3-small` por defecto) tras el adaptador `openai_text` / `openai_embeddings` |
| Visión | **GLM** (Z.ai, `glm-5.3-flash` por defecto) tras el adaptador `glm_vision` |
| Observabilidad | **Langfuse Cloud** tras `observability/langfuse_adapter.py` (no-op si no está configurado) |

El reto sugiere Groq y Google AI Studio; se usaron OpenAI y GLM por disponibilidad de claves. Cambiar de proveedor es añadir un adaptador en `app/ai/providers/` y seleccionarlo por variable de entorno.

## Desarrollo local

### Prerrequisitos

- Node `>=22` y npm 11.
- [`uv`](https://docs.astral.sh/uv/) (gestiona Python 3.12 y las dependencias de `apps/api`).
- Un proyecto de Supabase (para login real). SQLite basta para la API en local; PostgreSQL/Supabase solo para validar el dialecto canónico.

### Instalación y ejecución

```bash
npm install            # workspaces web + turbo
npm run api:sync       # uv sync en apps/api (crea .venv)
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env

npm run api:migrate    # alembic upgrade head (SQLite por defecto)
npm run api:dev        # uvicorn en http://localhost:8000
npm run dev:web        # Vite en http://localhost:5173
```

Alternativa sin `uv` (solo ejecución): `cd apps/api && pip install -r requirements.txt && uvicorn app.main:app`.

### Variables de entorno

Todas documentadas en `apps/api/.env.example` y `apps/web/.env.example`. Las esenciales:

| Variable | Uso |
| --- | --- |
| `CONTENT_SUITE_AUTH_JWT_SECRET`, `CONTENT_SUITE_AUTH_JWT_ISSUER` | Verificación del JWT de Supabase (audiencia `authenticated`). Sin ellas `/api/v1/me` responde 503. |
| `CONTENT_SUITE_DATABASE_URL` | `sqlite:///./content_suite_dev.db` por defecto; `postgresql+psycopg://…` en Supabase. |
| `CONTENT_SUITE_CORS_ORIGINS` | Orígenes permitidos (`*` en producción: auth por bearer, sin cookies). |
| `CONTENT_SUITE_BRAND_CREATION_ALLOWLIST` | Correos que pueden crear workspaces (`*` solo en local). |
| `CONTENT_SUITE_AI_PROVIDER=openai`, `CONTENT_SUITE_OPENAI_API_KEY` | Texto y embeddings. |
| `CONTENT_SUITE_VISION_PROVIDER=glm`, `CONTENT_SUITE_GLM_API_KEY` | Auditoría visual. |
| `CONTENT_SUITE_LANGFUSE_PUBLIC_KEY`, `..._SECRET_KEY`, `..._HOST` | Tracing (las tres, o no-op). |
| `CONTENT_SUITE_STORAGE_PROJECT_URL`, `..._SERVICE_KEY`, `..._BUCKET` | Storage privado (las tres, o 503 controlado al subir). |
| `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Cliente web. |

Sin claves de IA la app arranca y las capabilities fallan con `AIProviderNotConfiguredError` (503), nunca con contenido inventado.

### Seeds y tokens de desarrollo

```bash
cd apps/api
uv run python -m scripts.seed          # marca Kinu + 3 perfiles + membresías (idempotente)
uv run python -m scripts.dev_tokens    # tokens HS256 de 15 min para probar la API con curl/httpie
```

Los tokens sirven para la API directamente. Para navegar la app hay que iniciar sesión con una cuenta real de Supabase Auth; para probar un rol revisor, ese usuario necesita una fila en `brand_memberships` con el rol correspondiente. Una cuenta sin membresías ve el onboarding "Crea tu primer workspace" (`POST /api/v1/brands`, gateado por la allowlist).

### Checks

```bash
npm run lint           # ESLint (web)
npm run typecheck      # tsc -b (web)
npm run test           # vitest (web)
npm run build          # build de producción web
npm run api:lint       # ruff check
npm run api:typecheck  # ty check app
npm run api:test       # pytest (~520 tests, fakes deterministas; sin llamadas reales a proveedores)
cd apps/api && uv run ruff format --check .
```

Nota: `tests/test_trace_facade.py` asume Langfuse **no** configurado; si `apps/api/.env` tiene claves de Langfuse, ese test falla en local por diseño. Ejecutar la suite sin esas variables o en un shell limpio.

### Migraciones

```bash
npm run api:migrate                                   # SQLite local
cd apps/api
CONTENT_SUITE_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB' uv run alembic upgrade head
```

Nunca escribir credenciales reales en archivos versionados.

## Despliegue

- **API**: `render.yaml` (Blueprint) crea el web service con `uv sync --frozen --no-dev`, ejecuta `alembic upgrade head` al arrancar y usa `/health/ready` como health check. Los secretos se declaran con `sync: false` y se cargan en el Dashboard de Render.
- **Web**: `apps/web/vercel.json` reescribe todas las rutas a `index.html` (SPA). Variables `VITE_*` en el proyecto de Vercel.
- **Supabase**: migraciones Alembic sobre la base del proyecto; bucket privado `content-suite`; Auth con proveedor email/contraseña.

Detalle en `docs/DEPLOYMENT.md`.

## Estructura del repositorio

```text
apps/api/app/         módulos de dominio + ai/ + observability/ + storage/
apps/api/alembic/     migraciones (SQLite y PostgreSQL/pgvector)
apps/api/scripts/     seed.py, dev_tokens.py
apps/api/tests/       pytest (unit, contratos, migraciones, API)
apps/web/src/features/  brand-dna, creative, approvals, brand-audit, observability, dashboard, session, shell
docs/                 ADRs, seguridad, observabilidad, despliegue, UI/UX, testing
openspec/             specs aceptadas y changes 001–014 (proposal, design, tasks)
specs/                specs de alto nivel por módulo
```

## Limitaciones conocidas

- **Capas gratuitas**: Render suspende la API sin tráfico (primer request lento); Langfuse Cloud y Supabase en planes free.
- **Auditoría visual descriptiva**: el modelo de visión juzga reglas expresadas en texto (uso de logo, paleta, composición); no mide píxeles ni proporciones exactas. El score es informativo y la decisión es humana.
- **Proveedores**: OpenAI y GLM en lugar de Groq y Gemini (sugeridos, no obligatorios). Sin fallback automático entre proveedores.
- **Verificación E2E**: la suite automatizada usa fakes; el recorrido con proveedores reales se validó manualmente (ver `openspec/changes/008-visual-compliance/tasks.md` 8.3 y `009-content-governance/tasks.md` 5.1 para el checklist).
- **Deuda técnica menor**: `useFieldArray` con listas de strings usa `register` + `setValue` con un cast documentado en `BrandDnaDocumentForm.tsx`; el round-trip `upgrade → downgrade → upgrade` de Alembic se verificó en SQLite, y en PostgreSQL solo se ha ejecutado `upgrade head` (el despliegue lo aplica al arrancar), no el ciclo completo contra una base limpia.
- Fuera de alcance por diseño: publicación a redes, generación de imágenes, flujos de aprobación configurables, multi-tenant enterprise.

## Proceso de desarrollo

Implementación incremental con **OpenSpec**: cada change en `openspec/changes/<n>/` tiene `proposal.md`, delta specs, `design.md` y `tasks.md`. Las 14 changes (`001-foundation` … `014-dashboard-activity`) están completas. Las dependencias se verificaron con Context7/registry antes de instalarse (`package-lock.json`, `apps/api/uv.lock`).

La referencia visual es `starter-design/Content Suite.dc.html`: claymorphism azul con superficies `.clay-*`, primitives de shadcn/ui y la paleta Strawberry Red `#E63946`, Honeydew `#F1FAEE`, Frosted Blue `#A8DADC`, Steel Blue `#457B9D`, Deep Space Blue `#1D3557` (roles en `docs/UI_UX.md`).
