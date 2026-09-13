# Deployment

## Target

```text
Frontend: Vercel (Vite static build)
Backend: Render (FastAPI)
Database/Auth/Storage: Supabase
Observability: Langfuse Cloud
Repository: GitHub
```

## Backend command

La implementación final debe exponer un comando equivalente a:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

El build/deploy parte del monorepo: Turborepo orquesta las tareas de app y Render ejecuta el comando anterior desde `apps/api`, donde `uv.lock` fija las dependencias Python.

## Environment

Separar:
- local;
- preview/staging si el tiempo lo permite;
- production/demo.

## Health

```http
GET /health/live
GET /health/ready
```

`ready` no debe invocar modelos pagos en cada probe.

## Secrets

Solo por environment / secret manager.

Nunca en:
- repo;
- frontend bundle;
- screenshots;
- logs.
