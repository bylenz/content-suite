# ADR-003 — Supabase Auth + Backend Authorization

**Status:** Accepted

## Decision

Supabase autentica. FastAPI autoriza.

```text
Login -> Supabase Auth -> JWT -> FastAPI -> membership + role guard
```

## Rules

- frontend no es autoridad de permisos;
- no confiar en roles enviados por cliente;
- brand membership se resuelve server-side;
- endpoints verifican rol y recurso.
