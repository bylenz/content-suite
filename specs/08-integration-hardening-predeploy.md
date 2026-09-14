# Objective

Validar localmente la integración completa y preparar una entrega manual segura. Esta spec termina antes de cualquier despliegue.

# Current State

Las specs 01–07 deben estar completas. Hay verificación web/API local y SQLite, pero aún falta un round-trip seguro en PostgreSQL/Supabase y E2E completo. Deployment está explícitamente prohibido.

# In Scope

- Consolidar README/env examples/checklists sin secretos.
- Ejecutar instalación, lint, formatting, typecheck, pruebas, build, arranque API, migraciones locales y health checks.
- Verificar PostgreSQL/Supabase sólo contra credenciales de desarrollo seguras aportadas por el usuario: upgrade→downgrade→upgrade, sin producción.
- Validar el flujo Creator → generation/edit → submit → changes → resubmit → content approval → visual upload/audit → visual decision.
- Validar trazas, fail-safe sin Knowledge/proveedor, CORS/Auth/RBAC, signed URLs y reducción de movimiento.
- Registrar límites reales y checklist de deploy sin ejecutar comandos de deploy.

# Out of Scope

- Desplegar web/API, migrar producción, tocar DNS, publicar a Vercel/Render, crear infraestructura productiva o ejecutar migraciones de Supabase producción.

# Domain / Modules Affected

Todos, sólo para prueba, documentación y correcciones de integración estrechamente necesarias.

# Database Changes

No crear cambios de esquema salvo corrección imprescindible descubierta durante una migración local/dev; cualquier corrección debe regresar a la spec de dominio correspondiente.

# API Changes

No añadir endpoints de producto; sólo health/readiness o correcciones contractuales justificadas.

# Frontend Changes

No rediseñar UI aprobada; corregir sólo estados, accesibilidad, responsive o integración real.

# AI / RAG Changes

Usar fakes por defecto. Probar proveedores/Langfuse reales sólo con claves de desarrollo provistas y nunca como requisito de la suite normal.

# Security / RBAC Requirements

Secret scan; ningún secreto en git/logs; JWT/role/membership server-side; storage privado; signed URL y filtros Knowledge brand/version verificados.

# Observability Requirements

Comprobar presencia de trace en cada capability AI y sanitización de metadata.

# Acceptance Criteria

- Todas las suites locales están verdes y la API/web arrancan.
- Migraciones aplican limpias en SQLite y, cuando existan credenciales de desarrollo, PostgreSQL/Supabase no productivo.
- El flujo crítico completo funciona con fakes deterministas.
- El handoff enumera variables, servicios externos, comprobaciones manuales y límites no probados.
- No ocurrió deployment.

# Tests Required

Todos los comandos root/web/API; integration/E2E con fakes; migration round-trip; smoke CORS/auth; verificación manual desktop/móvil y reduced motion.

# Manual Verification Steps

Seguir el flujo crítico con los tres roles demo y la checklist de seguridad; adjuntar evidencia de comandos/salidas sin datos sensibles.

# Stop Condition

Detener inmediatamente antes de cualquier acción de deploy o migración productiva y entregar PRE-DEPLOY HANDOFF.
