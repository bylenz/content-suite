# Objective

Implementar Creative Studio para crear, versionar, generar, editar y enviar contenido usando Brand Knowledge recuperado y outputs AI estructurados.

# Current State

No existen módulos, tablas, rutas ni pantallas Creative. El shell conserva Creative Studio como placeholder no interactivo. Brand DNA y Brand Knowledge (spec 03) serán las fuentes de contexto.

# In Scope

- `creative_items` y `creative_versions` con tipos PRODUCT_DESCRIPTION, VIDEO_SCRIPT e IMAGE_PROMPT, versiones inmutables y relación a la versión exacta de Brand DNA.
- Servicios para crear item, generar/regenerar mediante AI Platform, edición humana como versión nueva, listar/ver versiones, consistency check, applied context y submit.
- Guard que exige Brand Knowledge mandatory SYNCED para generar/check/submit cuando aplique.
- UI Creator para listado, creación, editor por tipo, historial, contexto aplicado, generación y manejo de 409/503; habilitar la navegación solo cuando el contrato esté disponible.

# Out of Scope

- Aprobar/rechazar contenido, subir visuales, generar imágenes, publicar en redes o permitir al reviewer editar.

# Domain / Modules Affected

Nuevo módulo `creative`, `knowledge`, `ai`, `observability`, shell/rutas frontend.

# Database Changes

Crear tablas `creative_items` y `creative_versions`, enums, FK de brand y Brand DNA version, índice de item/version y campos de output/brief/context/score/trace.

# API Changes

Implementar endpoints Creative documentados en `API.md`, con contratos Pydantic y envelopes de error; commands mutables deben tolerar retry/idempotency según su semántica.

# Frontend Changes

Agregar rutas y feature Creative Studio siguiendo `starter-design`: superficies editoriales densas, CTA azul selectivo y estados reales; no convertir Dashboard aprobado ni simular métricas.

# AI / RAG Changes

Generación y consistency check usan prompt registry, context builder por tarea, adapters y structured outputs Pydantic. Persistir sólo output, rule IDs aplicados, summary/checks/score y trace ID; nunca raw chain-of-thought.

# Security / RBAC Requirements

Creator crea/genera/edita/envía solo recursos de su brand; reviewers y visual reviewers tienen únicamente lectura autorizada. Toda comprobación es backend.

# Observability Requirements

Trazar generación/regeneración/check con item/version, Brand DNA, rule IDs, prompt/model version, latencia y resultado resumido.

# Acceptance Criteria

- Cada edición/regeneración crea una versión nueva y no muta una enviada.
- Generar sin Knowledge mandatory falla seguro con 503.
- Applied context identifica la versión Brand DNA y reglas usadas.
- La UI muestra datos reales y estados de error/carga/vacío.

# Tests Required

Fakes de texto; permisos; invariantes de versión; falta de Knowledge; contratos estructurados inválidos; API+DB por tipo; navegación/UI state mínimo.

# Manual Verification Steps

Como Creator: crear item, generar, editar a nueva versión, revisar contexto, ejecutar consistency check y enviar. Confirmar que un reviewer no puede editar.

# Stop Condition

Detener si una versión enviada se modifica, si generation llama un proveedor desde router o si Knowledge obligatorio se omite.
