## Context

- Disponible hoy: AI Platform (005) con puertos `TextModel`/`VisionModel`/`EmbeddingModel` y `VisionModel.analyze_structured` ya definido en `app/ai/ports.py`; Knowledge (006) con context builder por tarea (`VISUAL` incluye mandatory + semántico scope `VISUAL`+`BOTH`) y `KnowledgeNotAvailableError`; identity con `authorize_brand_action` y orden membership-first validado; envelope centralizado de errores en `app/errors.py`; patrón RLS de la change 007 (RLS enabled + SELECT member-scoped para `authenticated`, sin policies de escritura).
- En vuelo por otro agente: change 007 (RLS hardening) y las specs 04 (Creative) / 05 (Governance), prerrequisitos duros de esta change: `creative_items.workflow_status = CONTENT_APPROVED` y `workflow_events` no existen aún. Esta change se implementa después de que 04/05 estén en el repo.
- SQLite es el motor de dev/test (seam documentado en 006): RLS y signed URLs reales solo existen en PostgreSQL/Supabase; la suite usa fakes.

## Goals / Non-Goals

**Goals:**
- Módulo `storage` como puerto reutilizable (upload privado, validación, signed URLs) sin conocimiento del dominio de visuales.
- Módulo `visual_audit` con el ciclo completo upload → audit → decisión humana, fail-safe ante Knowledge visual ausente.
- Score determinista calculado en backend; decisiones inmutables con excepción HIGH auditada.
- Trazabilidad sanitizada coherente con 005/006 (`CapabilitySpan` existente, sin romper su suite).

**Non-Goals:**
- Generación de imágenes, editor gráfico, bucket público, revisión configurable ni aprobación automática por score (out of scope de la spec 06).
- Reintentos asíncronos/colas para auditorías (sin razón medible, ARCHITECTURE).
- RLS retroactivo de tablas ajenas (pertenece a 007).

## Decisions

### D1: Dos módulos con dependencia unidireccional
`storage` expone un puerto (`put_object`, `signed_url`, `remove_object`) sin semántica de dominio; `visual_audit` lo consume y añade versionado, workflow y decisiones. `storage` no importa `visual_audit` ni `creative`. Alternativa descartada: lógica de storage dentro de `visual_audit` — bloquearía reuso por `brand_dna` (brand assets, spec futura) y mezclaría infraestructura con dominio.

### D2: Adapter Supabase Storage aislado, resolver env-gated, fake en tests
SDK de Supabase (storage client) importado solo en `app/storage/providers/supabase_storage.py`; resolver construye el adapter solo con configuración completa (URL del proyecto + service key + bucket), igual que el patrón OpenAI de 006; configuración parcial → adapter `None` → 503 controlado. `signed_url` usa expiración corta configurada (default 300s). Instalación del SDK con `uv` tras verificación Context7/docs oficiales (tarea de implementación). Tests corren contra `FakeStorage` determinista.

### D3: Validación de archivo sin dependencias del sistema
Detección de tipo real por magic bytes implementada en Python puro para los tipos permitidos (PNG `89 50 4E 47`, JPEG `FF D8 FF`, WebP `RIFF....WEBP`) más límite de tamaño configurable (default 5 MB). Alternativas descartadas: `python-magic` (requiere libmagic del sistema, rompe portabilidad de tests) y confiar en el content type declarado (falsificable). Orden: validar tamaño → validar magic bytes → subir a storage → insertar fila en una transacción; si la transacción falla, compensación best-effort `remove_object` para no dejar huérfanos.

### D4: Signed URLs al leer, nunca rutas internas
Las respuestas de visual assets (cola, detalle, listado) computan `signed_url` en el boundary del router llamando al puerto storage; la columna `storage_path` nunca sale en responses. El frontend solo recibe la URL temporal. Alternativa descartada: endpoint dedicado de firmado — añade superficie API sin necesidad (los endpoints de lectura ya autorizan).

### D5: Score determinista como política de dominio pura
`compute_score(findings) = max(0, 100 − Σ penalización)` con penalización por finding en estado fail: HIGH 25, MEDIUM 10, LOW 3. Función pura en `visual_audit/policies.py`, testeada como determinista (mismos findings → mismo score, sin invocar modelo). El audit NO transiciona workflow: correr la auditoría no aprueba ni rechaza (stop condition).

### D6: Contrato de findings y fail-safe de output
`VisionFinding` Pydantic (`rule_id, category, severity: HIGH|MEDIUM|LOW, status: PASS|FAIL, expected, detected, evidence, recommendation`) con `extra="forbid"`; la auditoría valida la lista completa antes de persistir. Output inválido del modelo → 503 (código `VISION_OUTPUT_INVALID` en envelope) sin persistir auditoría. Prompt registrado en el prompt registry de `ai` (patrón 005) con `prompt_version` propio; el service de `visual_audit` construye el prompt desde el contexto Knowledge y persiste `brand_dna_version_id` + conteo de reglas aplicadas en la auditoría.

### D7: Decisiones inmutables + excepción HIGH con evidencia
`visual_reviews` insert-only (sin UPDATE en la app; el repo no expone mutación). Aprobación con ≥1 finding HIGH fail exige `exception_accepted=true` y persiste en la decisión la evidencia (`finding_id`/`rule_id`/severity de los HIGH); sin la marca → 422. Idempotencia de decisión: si ya existe decisión del mismo reviewer sobre la misma auditoría con el mismo payload, se devuelve la existente (chequeo antes de insert + constraint único `(visual_audit_id, reviewer_id, decision)` como red de seguridad contra carrera). Transiciones: approve → `FINAL_APPROVED`, request-changes → `VISUAL_CHANGES_REQUESTED`; ambas emiten `workflow_event` en la misma transacción.

### D8: Migración con RLS del patrón 007 desde el día uno
Una migración reversible crea `visual_assets`, `visual_audits`, `visual_reviews` (columnas según DATA_MODEL + `workflow_status` ya existente en `creative_items` por la spec 05) con índices por `creative_item_id`/`visual_asset_id` y RLS enabled + policies SELECT member-scoped (mismo predicado EXISTS sobre `brand_memberships` que 007; sin policies de escritura para nadie). Coordina con 007 para no duplicar el mecanismo: si 007 extrae un helper de policies, esta migración lo reutiliza.

### D9: Frontend — feature `brand-audit` y extensión de Creative
Nueva feature `apps/web/src/features/brand-audit` (cola, detalle de asset con signed URL, findings/evidencia, historial, panel de decisión con checkbox de excepción HIGH y confirmación explícita) solo activa para `VISUAL_REVIEWER` (nav por rol, UI_UX.md). El upload del Creator vive en Creative Studio (feature de la spec 04, extendida aditivamente) visible también en estados de feedback. Lenguaje visual de `starter-design`: cola y decisión con clay fuerte, findings y evidencia en superficies editoriales tenues; errores 403/409/503 mapeados a estados reales.

## Risks / Trade-offs

- [Prerrequisitos 04/05 en vuelo por otro agente] → Esta change no toca código hasta que 04/05 estén mergeados; el contrato de estados ya está fijado en WORKFLOWS.md y en los specs delta.
- [SQLite no ejecuta RLS ni firma URLs] → Tests de forma SQL offline de la migración (patrón 006) + `FakeStorage`; verificación manual contra Supabase queda documentada como tarea explícita, igual que en 006.
- [Compensación best-effort al fallar la transacción tras subir el objeto] → Puede quedar un objeto huérfano si el delete compensatorio falla; sin impacto de dominio (sin fila en DB) y limpieza operativa posterior; se registra el fallo sanitizado.
- [Peso del score arbitrario (25/10/3)] → Constantes de dominio documentadas; cambiarlas no altera contratos ni specs, solo tests de score.
- [Signed URL en cada lectura añade una llamada al puerto] → Fake en tests y TTL 300s default; el coste real es una llamada HTTP interna de Supabase, aceptable en el volumen MVP.

## Migration Plan

1. Merge de 04/05/007 (prerrequisitos) con `alembic upgrade head` aplicado.
2. Esta change: una migración nueva (3 tablas + RLS), `alembic downgrade -1` verifica reversibilidad.
3. Rollback: downgrade elimina tablas sin afectar las de 04/05/007; el código de visual audit queda sin efecto si se revierte después.

## Open Questions

Ninguna que bloquee specs, approach o tasks: los pesos del score y el TTL se fijaron como defaults configurables/documentados (D5, D2).
