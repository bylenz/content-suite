# Objective

Convertir Brand DNA publicado en Brand Knowledge recuperable mediante sync versionado, reglas obligatorias y recuperación semántica híbrida; bloquear consumidores cuando falte contexto requerido.

# Current State

Brand DNA ya publica versiones inmutables y conserva `knowledge_status`, pero no existen chunks, embeddings, sync, assets de marca ni endpoints Knowledge. AI Platform/EmbeddingModel llega de la spec 02.

# In Scope

- Modelos, migración y repositorio para `brand_knowledge_chunks` con `brand_id`, `brand_dna_version_id`, sección, tipo de regla, scope, mandatory, contenido y metadata.
- Soporte PostgreSQL/pgvector canónico y estrategia de test SQLite sin fingir búsqueda vectorial productiva.
- Servicio de sync explícito desde una versión ACTIVE: chunk determinista, embedding adapter, estados `NOT_SYNCED → SYNCING → SYNCED|FAILED` y retry idempotente.
- Marcar Knowledge OUTDATED solo bajo las reglas ya acordadas de Brand DNA.
- Context builder: reglas mandatory + top-k semántico filtrado estrictamente por marca y versión, segmentado por tarea TEXT/VISUAL.
- Endpoints status, lectura y sync con RBAC; Creator inicia sync, reviewers leen solo información permitida.
- Base para brand assets privados únicamente si son imprescindibles para contexto visual; upload completo pertenece a spec 06.

# Out of Scope

- Generar contenido, revisión humana, visual audit, UI de Creative o fallback de generación sin Knowledge.

# Domain / Modules Affected

`brand_dna`, nuevo módulo `knowledge`, `ai` y configuración PostgreSQL.

# Database Changes

Crear `brand_knowledge_chunks` e índices de brand/version/mandatory/scope. Configurar/extender `vector` solo para PostgreSQL con migración reversible y documentar la limitación SQLite.

# API Changes

Implementar contratos de `GET /brands/{brand_id}/brand-knowledge`, `GET .../status` y `POST .../sync`; normalizar 403/404/409/503 con el envelope existente.

# Frontend Changes

Mostrar el estado real de Knowledge en superficies existentes sin prometer sincronización automática ni habilitar Creative antes de que exista.

# AI / RAG Changes

- Embeddings tras adapter, nunca desde router.
- Recuperación híbrida con mandatory context siempre presente y búsqueda semántica filtrada por `brand_id` y `brand_dna_version_id` antes de cualquier ranking.
- Si falta Knowledge mandatory, retornar 503 controlado al consumidor.

# Security / RBAC Requirements

Validar membresía antes de leer/sincronizar; no filtrar chunks de borrador a reviewers; no mezclar vectores entre brands/versiones.

# Observability Requirements

Trazar sync, embedding y retrieval con versión Brand DNA, conteo de chunks y resultado sanitizado.

# Acceptance Criteria

- Una versión ACTIVE puede sincronizarse de forma idempotente y su status refleja éxito/error real.
- Un cambio de Brand DNA no sobrescribe chunks de una versión publicada.
- Retrieval devuelve mandatory + contexto semántico solo de la marca/versión solicitadas.
- Cualquier consumidor falla seguro si mandatory Knowledge no está disponible.

# Tests Required

Unit de chunking/context builder; integración de sync/RBAC/idempotencia/FAILED; filtros brand y version; migración SQLite round-trip y PostgreSQL documentado; fake embedding adapter.

# Manual Verification Steps

Crear/publicar Brand DNA Kinu, sincronizar, revisar status y confirmar que un reviewer no ve borrador ni datos de otra marca.

# Stop Condition

Detener si pgvector se usa como fuente de verdad, si retrieval no filtra brand y versión antes de ranking, o si la app genera sin mandatory context.
