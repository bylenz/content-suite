# Testing

## Pirámide práctica

### Unit
Prioridad alta:
- permission policies;
- state transitions;
- deterministic scoring;
- context builder;
- Pydantic contracts.

### Integration
- repositories;
- migrations;
- pgvector filters;
- API + DB;
- storage abstraction.

### Contract
- AI adapter fake devuelve schema válido;
- schema inválido falla de forma controlada.

### E2E crítico

```text
Creator creates/generates
-> submits
-> Content Reviewer requests changes
-> Creator resubmits
-> reviewer approves
-> visual submitted
-> audit
-> Visual Reviewer approves
```

## External providers

CI no debe requerir llamadas reales a LLM/Vision.

Usar fake adapters.

Real provider smoke tests:
- manuales;
- opcionales;
- fuera del test suite principal.

## Tooling de pruebas

Turborepo orquesta las tareas de ambos apps desde la raíz cuando corresponda. Las tareas Python permanecen bajo `uv`: usar `uv run pytest`, `uv run` para lint/typecheck y `uv run alembic` para migration sanity; no invocar `pip` ni un entorno manual.

## OpenSpec

Cada change se valida antes de entregar con `npx @fission-ai/openspec@latest validate <nombre> --strict`. Las pruebas y comandos deben corresponder a los escenarios y tasks de esa change.

## Minimum before merge

Frontend:
- lint;
- typecheck;
- relevant tests;
- build.

Backend:
- `uv sync`;
- lint/format;
- typecheck si configurado;
- `uv run pytest`;
- migration sanity.
