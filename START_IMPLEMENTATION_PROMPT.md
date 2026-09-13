# Start Implementation Prompt

Use this prompt with the main implementation agent.

---

You are the primary implementation agent for the Content Suite technical challenge.

Your goal in this run is **NOT to implement the whole product**.

Implement only the active OpenSpec change:

`openspec/changes/001-foundation/`

## Mandatory context

Read in this order:

1. `PROJECT_CONTEXT.md`
2. `ARCHITECTURE.md`
3. `MODULES.md`
4. `AGENTS.md`
5. `openspec/config.yaml`
6. `docs/UI_UX.md`, `starter-design/Content Suite.dc.html` y la captura de referencia

Después ejecuta:

```bash
npx @fission-ai/openspec@latest instructions apply --change 001-foundation --json
```

Lee todos los archivos que el resultado incluya en `contextFiles`. Esos artefactos son el contrato; no supongas una lista fija de archivos.

Then read only the additional documents necessary for this change:
- `DATA_MODEL.md`
- `docs/adr/001-modular-monolith.md`
- `docs/adr/002-database-choice.md`
- `docs/adr/003-auth-strategy.md`
- `docs/TESTING.md`
- `docs/SECURITY.md`

Do not preload unrelated documents unless implementation requires them.

## Locked technical decisions

Repository and dependencies:
- npm workspaces + Turborepo; Turbo orquesta las tareas, no crea microservicios
- antes de agregar o actualizar **cada** librería, resolverla y consultar su documentación actual con Context7; si no existe una entrada exacta, verificar la fuente oficial y el registry. Instalar la versión estable actual compatible y dejar el lockfile actualizado
- dependencias frontend: instalar desde la raíz en `apps/web` con npm workspaces
- dependencias backend: gestionar exclusivamente con `uv` en `apps/api` (`uv add`, `uv sync`, `uv run`); no usar `pip`, `requirements.txt` ni Poetry

Frontend:
- Vite
- React
- TypeScript
- Tailwind
- React Router
- TanStack Query
- usar `starter-design/Content Suite.dc.html` y la captura como guía visual de todas las pantallas y secciones, implementando solo el shell y flujos de la change
- instalar `claymorphism-css` después de validarlo con Context7; usarlo para una materialidad clay azul más marcada en superficies elevadas, sin sacrificar contraste o contenido denso
- usar exclusivamente la paleta canónica: Strawberry Red `#E63946`, Honeydew `#F1FAEE`, Frosted Blue `#A8DADC`, Steel Blue `#457B9D` y Deep Space Blue `#1D3557`; consultar sus roles en `docs/UI_UX.md`

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic

Platform:
- Supabase PostgreSQL
- Supabase Auth
- Supabase Storage later
- pgvector later
- Langfuse later

Architecture:
- modular monolith
- FastAPI is the authority for RBAC and workflow rules

## Working style

First inspect the repository, la configuración de Turbo y la pantalla equivalente en `starter-design/` antes de crear frontend.

Luego, antes de cada instalación, usa Context7 para confirmar la documentación y versión estable actual de esa librería.

Then produce a short implementation plan tied directly to los requirements, escenarios y tasks entregados por OpenSpec.

After the plan, implement the spec.

You may delegate focused subtasks to subagents if available, but you remain responsible for architectural consistency and final verification.

Suggested delegation:
- frontend bootstrap;
- backend bootstrap;
- database/auth foundation;
- tests/reviewer.

Do not allow subagents to make architecture decisions independently.

## Hard rules

- Follow `AGENTS.md`.
- Do not implement future OpenSpec changes.
- No marques una task como completa hasta que su verificación pase.
- Do not add Redux.
- Do not add microservices.
- No copies el HTML/JavaScript de `starter-design/`; reconstruye en React únicamente los elementos de la change.
- Conserva el sistema de todas las secciones de la referencia: sidebar elevada, navegación azul acolchada, tarjetas suaves, paneles azul profundo, métricas pastel y CTAs con relieve. No extiendas el clay a cada input, tabla o línea de texto.
- Do not add Celery, Redis, Kafka, RabbitMQ or Kubernetes.
- Do not integrate AI providers yet.
- Supabase MCP ya está configurado localmente para el proyecto y solicita OAuth al primer uso; no leer, editar ni versionar `.pi/supabase.json` ni credenciales OAuth.
- Do not add abstractions that are not required by the foundation.
- Do not place authorization logic only in the frontend.
- Do not hardcode demo users into domain logic.
- Never commit secrets.
- Prefer small, typed, testable modules.

## Required verification

Before finishing:

Repository / frontend:
- las instalaciones se ejecutan por workspace y Turbo puede orquestar sus tareas desde la raíz;
- install succeeds;
- lint succeeds;
- TypeScript check succeeds;
- production build succeeds.

Backend:
- `uv sync` succeeds;
- migrations can be applied;
- `uv run pytest` succeeds;
- FastAPI app starts through `uv run`;
- health endpoints work.

Verify frontend can reach backend health endpoint.

OpenSpec:
- marcar cada task inmediatamente después de completar y verificar su trabajo;
- `npx @fission-ai/openspec@latest validate 001-foundation --strict` succeeds;
- reportar el estado final de la change, pero no archivarla.

## Final response

Return:

1. what was implemented;
2. final repository tree for relevant files;
3. commands executed and their results;
4. tests added;
5. dependencias instaladas, versiones y consultas Context7 realizadas;
6. assumptions;
7. known issues/debt;
8. estado y validación OpenSpec;
9. recomendar la siguiente change, sin crearla.

Then STOP.

Do not archive `001-foundation` or begin Brand DNA implementation until explicitly instructed.
