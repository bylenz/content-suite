## Why

Content Suite necesita una base ejecutable antes de desarrollar sus capacidades de producto. La primera entrega debe fijar el monorepo, las fronteras de autenticación y persistencia, y una base visual coherente sin adelantar módulos de negocio.

## What Changes

- Crear `apps/web` y `apps/api` dentro del monorepo con Turborepo como orquestador de tareas.
- Establecer el frontend Vite/React y el backend FastAPI gestionado exclusivamente con `uv`.
- Crear los endpoints de salud, la frontera de autenticación y la primera migración de identidad y marcas.
- Configurar Supabase MCP localmente para el proyecto, con OAuth y capacidades restringidas al proyecto de desarrollo.
- Añadir el shell frontend y sus primitives mínimos según `starter-design/`, con un lenguaje claymorphism más marcado mediante Clay CSS.
- Añadir verificaciones básicas para salud, autorización, roles y comunicación web-API.

## Capabilities

### New Capabilities
- `foundation`: Define la base ejecutable, el tooling del monorepo, las fronteras de autenticación y las comprobaciones mínimas para iniciar el producto.

### Modified Capabilities
- Ninguna.

## Impact

Afecta la configuración raíz de Turborepo, los nuevos workspaces `apps/web` y `apps/api`, dependencias npm y `uv`, migraciones iniciales, la documentación de desarrollo y los tests de foundation. No introduce lógica de Brand DNA, RAG, generación AI, revisiones ni auditoría visual.
