## Why

El flujo de producto termina en auditoría visual multimodal y decisión humana final (PROJECT_CONTEXT), pero hoy no existen visual assets, storage privado, auditoría Vision ni aprobación visual: la spec 06 es la última capacidad de dominio pendiente y depende de que Creative (spec 04) y Governance (spec 05) provean items `CONTENT_APPROVED`. Sin esta change, Content Suite no puede cerrar el ciclo `CONTENT_APPROVED → visual versionado → audit → FINAL_APPROVED` ni demostrar las invariantes "audit falla seguro sin Knowledge visual" y "solo el Visual Compliance Reviewer decide".

## What Changes

- Nuevo módulo `apps/api/app/storage`: puerto de storage privado con validación server-side de archivo (tipo permitido por magic bytes, tamaño máximo, tipos permitidos acotados a imagen), paths por marca/item sin conjeturas de cliente, URLs firmadas de corta duración y nada público por defecto. Adapter Supabase Storage aislado (imports del SDK solo en el adapter) con resolver env-gated y fake determinista para tests.
- Nuevas tablas `visual_assets`, `visual_audits` y `visual_reviews` vía migración reversible: versiones inmutables de visual (`UNIQUE(creative_item_id, version)`), findings estructurados y score persistidos por auditoría, decisiones de reviewer con `exception_accepted`, RLS coherente con el patrón de la change 007 (SELECT member-scoped, sin policies de escritura).
- Nuevo módulo `apps/api/app/visual_audit`: upload de visual solo sobre creative items `CONTENT_APPROVED` (409 en otro estado, 403 sin rol/membresía), auditoría vía el puerto `VisionModel` de AI Platform (005) consumida solo desde el service de dominio, context builder visual obligatorio (mandatory + semántico scope VISUAL/BOTH vía Knowledge 006) que falla seguro con 503 si falta, contrato Pydantic de findings `rule_id/category/severity/status/expected/detected/evidence/recommendation`, score determinista calculado en backend a partir de los findings persistidos, y decisión final exclusiva de `VISUAL_REVIEWER` con excepción HIGH explícita (`exception_accepted=true` + evidencia persistida).
- Endpoints de Visual Review de `API.md`: cola, upload/listado de assets por item, disparo y lectura de audit, approve/request-changes por audit, historial visual por item; envelopes 403/404/409/422/503 con el sistema centralizado existente; idempotencia en approve/request-changes.
- Workflow extendido aditivamente: `CONTENT_APPROVED → PENDING_VISUAL_REVIEW` al subir el primer visual; `VISUAL_CHANGES_REQUESTED → PENDING_VISUAL_REVIEW` con nueva versión; `PENDING_VISUAL_REVIEW → FINAL_APPROVED` al aprobar; todo con `workflow_events` (append-only, spec 05).
- Frontend: feature Brand Audit para Visual Compliance Reviewer (cola, detalle de asset vía signed URL tras validación, findings/evidencia, historial y decisión con excepción HIGH), y en Creative Studio el Creator sube visuales y observa estado/feedback; navegación habilitada solo para Visual Reviewer según `docs/UI_UX.md`, preservando el lenguaje visual de `starter-design`.

## Capabilities

### New Capabilities
- `private-storage`: puerto de storage privado con validación server-side de tipo/tamaño, organización de paths por marca/item, signed URLs de corta duración, nada público por defecto, adapter Supabase Storage aislado y fake para tests.
- `visual-compliance`: versionado inmutable de visuales ligados a items `CONTENT_APPROVED`, auditoría multimodal con contexto visual mandatory fail-safe, findings estructurados validados con Pydantic, score determinista en backend, decisión humana exclusiva del Visual Compliance Reviewer con excepción HIGH auditada, endpoints Visual Review con RBAC membership-first y trazabilidad sanitizada.

### Modified Capabilities
- Ninguna (el workflow `creative_items.workflow_status` gana sus estados visuales según WORKFLOWS.md; la extensión es aditiva y pertenece al contrato de esta change, no modifica artifacts de 04/05).

## Impact

- `apps/api`: nuevos módulos `storage` (ports, provider adapter, resolver, service, errors) y `visual_audit` (models, schemas, repository, policies, service, router, errors); migración Alembic nueva (3 tablas + índices + RLS coherente con 007); settings nuevas de storage (bucket, TTL de signed URL, tamaños/tipos permitidos); registro de errores en `app/errors.py`; tests nuevos (fake storage, validación, RBAC, workflow states, score determinista, findings Pydantic, falta de Knowledge, migraciones, API integration).
- `apps/api` dependencias: cliente de Supabase Storage verificada con Context7/documentación oficial e instalada con `uv`, importada solo dentro del adapter; sin dependencias nuevas en frontend.
- `apps/web`: nueva feature `brand-audit`; extensión de Creative Studio con upload/estado de visual; navegación por rol extendida; sin cambios en superficies aprobadas de Dashboard/Brand DNA.
- Prerrequisitos duros: specs 04 (Creative Studio) y 05 (Content Governance) implementadas — upload exige items `CONTENT_APPROVED` y workflow_events; Knowledge visual (006) ya disponible (chunks scope VISUAL/BOTH y builder VISUAL).
- Coordinación con change 007 (RLS hardening, otro agente): las tablas nuevas se crean ya con RLS y policies del patrón 007 para no introducir diferidos de hardening.
