# Content Suite

Plataforma AI-first para mantener consistencia de marca durante la creación y aprobación de contenido.

## Objetivo del reto

Content Suite implementa cuatro capacidades principales:

1. **Brand DNA Architect** — crea y versiona la fuente de verdad de una marca.
2. **Creative Studio** — genera contenido usando Brand Knowledge recuperado mediante RAG.
3. **Governance + Brand Audit** — separa revisión semántica y cumplimiento visual multimodal.
4. **Observability** — traza contexto recuperado, prompts, modelos, respuestas y latencias con Langfuse.

## Roles

- **Creator** — crea Brand DNA y contenido.
- **Content Reviewer** — revisa el contenido y solicita cambios o aprueba.
- **Visual Compliance Reviewer** — ejecuta auditoría multimodal y toma la decisión final sobre el visual.

## Stack

### Frontend
- npm workspaces + Turborepo para el monorepo
- React
- Vite
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod

### Backend
- `uv` para dependencias, entorno y ejecución
- FastAPI
- Python 3.12+
- Pydantic
- SQLAlchemy 2
- Alembic

### Plataforma
- Supabase PostgreSQL
- pgvector
- Supabase Auth
- Supabase Storage
- Langfuse

### AI
- Text model behind adapter interface
- Vision model behind adapter interface
- Embedding model behind adapter interface
- Initial text provider: Groq-compatible adapter
- Initial vision provider: Gemini-compatible adapter

## Arquitectura

El sistema usa un **monorepo estructurado con Turborepo**. `apps/api` es un **modular monolith** en FastAPI; PostgreSQL contiene el estado canónico y pgvector una representación derivada del Brand Knowledge.

Turborepo orquesta tareas entre apps. npm workspaces gestiona el frontend y `uv` gestiona exclusivamente el backend Python. Antes de instalar o actualizar cualquier librería, se consulta Context7 para comprobar su documentación y versión estable compatible; si no dispone de una entrada exacta, se verifica la fuente oficial y el registry.

Pi usa `pi-supabase` como MCP local del proyecto. Su configuración y cualquier material de OAuth se ignoran en Git; al primer uso, aceptar la confianza del proyecto y ejecutar `/supabase connect` para autorizar el endpoint oficial de Supabase.

`starter-design/Content Suite.dc.html` y la captura de referencia son la autoridad visual de todas las pantallas y secciones. La implementación conserva su jerarquía operativa, superficies suaves, acento azul y estados pastel, con un claymorphism azul más marcado mediante Clay CSS en tarjetas, navegación, CTAs y badges. El relieve se reduce en formularios y contenido denso para preservar contraste y escaneabilidad. La paleta canónica es Strawberry Red `#E63946`, Honeydew `#F1FAEE`, Frosted Blue `#A8DADC`, Steel Blue `#457B9D` y Deep Space Blue `#1D3557`; ver roles de cada color en `docs/UI_UX.md`. Se implementan solo los flujos incluidos en la change activa.

Antes de modificar arquitectura, leer:

1. `PROJECT_CONTEXT.md`
2. `ARCHITECTURE.md`
3. `MODULES.md`
4. `DATA_MODEL.md`
5. `WORKFLOWS.md`
6. `AI_SYSTEM.md`
7. `API.md`
8. `AGENTS.md`

## Desarrollo local (foundation)

### Prerrequisitos

- Node `>=22` y npm 11 (raíz, npm workspaces)
- [`uv`](https://docs.astral.sh/uv/) (gestiona Python 3.12 y todas las dependencias de `apps/api`)
- PostgreSQL/Supabase solo para validar la migración en el dialecto canónico; el resto usa SQLite local

### Instalación

```bash
npm install            # workspaces web + turbo (raíz)
npm run api:sync       # uv sync en apps/api (crea .venv)
```

### Ejecución

```bash
npm run dev:web        # Vite en http://localhost:5173
npm run api:dev        # uvicorn en http://localhost:8000 (requiere CONTENT_SUITE_AUTH_JWT_SECRET)
```

Variables de entorno (ver `apps/api/.env.example` y `apps/web/.env.example`):

- `CONTENT_SUITE_AUTH_JWT_SECRET` — secreto HS256 compatible Supabase; sin él, `/api/v1/me` responde 503.
- `CONTENT_SUITE_AUTH_JWT_ISSUER` — issuer esperado (`https://<project-ref>.supabase.co/auth/v1`); se valida junto con la audiencia `authenticated`.
- `CONTENT_SUITE_DATABASE_URL` — por defecto `sqlite:///./content_suite_dev.db`; el objetivo canónico es `postgresql+psycopg://…` (Supabase).
- `VITE_API_URL` — base de la API para el cliente web (por defecto `http://localhost:8000`).

El shell web arranca anónimo: la entrada al workspace demo es explícita desde la vista de sesión faltante y es solo presentación (no autentica). La API acepta CORS desde `http://localhost:5173`.

### Checks (raíz)

```bash
npm run lint           # ESLint (web) vía Turbo
npm run typecheck      # tsc -b (web) — solo el workspace web; la API se typechequea con api:typecheck
npm run build          # build de producción web
npm run test           # Turbo: hoy no hay tareas de test en web (exclusión documentada en la change); backend usa api:test
npm run api:lint       # ruff check (apps/api)
npm run api:typecheck  # ty check app (apps/api)
npm run api:test       # pytest (apps/api)
cd apps/api && uv run ruff format --check .   # formato backend
```

### Migraciones (Alembic)

```bash
# SQLite local (por defecto)
npm run api:migrate                                  # alembic upgrade head
# Dialecto canónico (Supabase PostgreSQL) — contra una base limpia:
cd apps/api
CONTENT_SUITE_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB' uv run alembic upgrade head
CONTENT_SUITE_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB' uv run alembic downgrade base
CONTENT_SUITE_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB' uv run alembic upgrade head
```

Nunca escribir credenciales reales en archivos versionados; usar variables de entorno.

### Dependencias y versiones comprobadas

Instaladas con Context7/registry verificados; lockfiles: `package-lock.json` (npm) y `apps/api/uv.lock` (uv).

| Área | Dependencia | Versión |
| --- | --- | --- |
| raíz | turbo | 2.10.12 |
| web | react / react-dom | 19.3.0 |
| web | react-router | 8.3.1 |
| web | @tanstack/react-query | 5.102.8 |
| web | claymorphism-css | 1.0.5 |
| web | vite | 8.3.0 |
| web | tailwindcss + @tailwindcss/vite | 4.3.3 |
| web | typescript | 5.9.3 (types-eslint requiere <6.1.0) |
| web | eslint + @eslint/js | 10.10.0 / 10.0.1 |
| api | fastapi | 0.141.1 |
| api | pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| api | sqlalchemy | 2.0.52 |
| api | alembic | 1.20.0 |
| api | psycopg[binary] | 3.3.5 |
| api | pyjwt | 2.14.0 |
| api | uvicorn | 0.52.4 |
| api (dev) | pytest / httpx | 9.1.1 / 0.28.1 |
| api (dev) | ruff | 0.16.7 |
| api (dev) | ty | 0.0.80 |

## Deuda conocida de foundation

Ítems de verificación pendientes de `001-foundation`; son seguimiento de verificación, no alcance de producto implementado:

- **Round-trip de migración en PostgreSQL/Supabase**: aún debe ejecutarse con credenciales seguras del proyecto contra una base limpia (hoy solo se verificó en SQLite). Ejecutar `upgrade head` → `downgrade base` → `upgrade head` con `CONTENT_SUITE_DATABASE_URL=postgresql+psycopg://…` antes de depender del dialecto canónico.
- **Revisión visual desktop/móvil**: se realizó con capturas reales de Chrome, pero la interacción por teclado del demo autenticado y del drawer móvil no pudo automatizarse en navegador porque el permiso de accesibilidad del SO no estaba disponible y no se agregó ninguna dependencia nueva de automatización.

## Desarrollo

La implementación se realiza incrementalmente con OpenSpec. Los contratos aceptados viven en `openspec/specs/`; cada trabajo nuevo se planifica en `openspec/changes/<change>/` con `proposal.md`, delta specs, `design.md` y `tasks.md`.

El primer trabajo activo es:

`openspec/changes/001-foundation/`

No implementar módulos posteriores hasta que las tareas de foundation estén completas, las validaciones pasen y la change haya sido validada. No archivarla ni iniciar otra change sin instrucción.
