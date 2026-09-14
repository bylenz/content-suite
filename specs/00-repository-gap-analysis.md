# Objective

Registrar el estado verificable del repositorio antes de ampliar el producto y separar el trabajo faltante en entregas seguras.

# Current State

- Implementado: monorepo Vite/React/Tailwind y FastAPI modular; JWT HS256 con issuer/audience/exp, membresías y RBAC en servidor; health checks; Brand DNA estructurado, versionado, con borrador privado para Creator, publicación idempotente y seeds Kinu/tokens de desarrollo.
- Implementado: Dashboard y Create/Edit/Read Brand DNA aprobados; `motion/react`, accesibilidad del drawer nativo y placeholders honestos para capacidades futuras.
- Implementado: dos migraciones (`identity`, `brand_dna_versions`) y 70 pruebas backend.
- Parcial: `knowledge_status` se persiste, pero no hay sincronización, chunks, embeddings ni recuperación.
- Ausente: AI Platform/adapters/prompts/tracing, Brand Knowledge/RAG, Creative, Governance, assets/Storage, Visual Audit, workflow events y facade/UI de observabilidad.
- Frontend solo enruta Dashboard y Brand DNA. Las rutas futuras son placeholders no interactivos.
- `claymorphism-css` es una dependencia directa e importa la clase base `.clay`; quitarla sin reemplazo rompería superficies aprobadas. shadcn/ui no está inicializado.
- No existe el directorio raíz `specs/` antes de este análisis; los contratos anteriores están en `openspec/changes/`.

# Architecture Alignment

La implementación existente respeta router → service → policy/repository y no sitúa autorización en el frontend. El drift principal es documental: `PROJECT_CONTEXT.md` y `API.md` describen capacidades MVP aún no implementadas. Este conjunto de specs convierte esas promesas en entregas dependientes y testeables; no se deben interpretar como disponibilidad actual.

# Required Sequence

1. Sustituir Clay CSS por primitives shadcn/Tailwind sin rediseñar UI aprobada.
2. Crear AI Platform y trazabilidad como base para toda llamada de proveedor.
3. Implementar Brand Knowledge/RAG y sincronización segura.
4. Implementar Creative Studio versionado.
5. Implementar Content Governance y workflow events.
6. Implementar Storage, visual assets y Visual Audit.
7. Exponer observabilidad de producto sin revelar datos sensibles.
8. Ejecutar hardening y validación pre-despliegue local; detenerse antes de desplegar.

# Stop Condition

No se modifica producto fuera de una spec de esta carpeta y de la change OpenSpec correspondiente. Dashboard y Create Brand DNA se preservan salvo corrección funcional, accesible o de la sustitución técnica de Clay CSS.
