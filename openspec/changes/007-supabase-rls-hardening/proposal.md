## Why

El despliegue a producción (Supabase) quedó bloqueado por el preflight de seguridad: las tablas de dominio ya migradas (`brands`, `profiles`, `brand_memberships`, `brand_dna_versions`, `brand_knowledge_chunks`) viven en el esquema `public` sin Row Level Security ni políticas, de modo que la Supabase Data API (PostgREST, expuesta por defecto con las claves `anon`/`authenticated`) puede leerlas y escribirlas sin pasar por la autorización de FastAPI. ADR-003 fija "Supabase autentica, FastAPI autoriza": la base de datos no puede quedar como superficie de acceso no autorizado.

## What Changes

- Habilitar `ENABLE ROW LEVEL SECURITY` en las cinco tablas existentes de `public` mediante una migración Alembic nueva, reversible, aplicada al final de la cadena existente (`c4a9b2e6f8d1`), solo en la rama PostgreSQL (Supabase canónico); SQLite (dev/test) permanece como no-op documentado porque no existe RLS allí.
- Políticas de solo lectura coherentes con la autorización del backend, sin confiar en roles del cliente:
  - `profiles`: un usuario autenticado solo puede leer su propia fila (`auth.uid() = id`); sin políticas de escritura.
  - `brand_memberships`: un usuario autenticado solo puede leer sus propias membresías (`auth.uid() = profile_id`); sin políticas de escritura.
  - `brands`, `brand_dna_versions`, `brand_knowledge_chunks`: solo lecturas para usuarios autenticados con membresía en la marca (`EXISTS` sobre `brand_memberships` con `profile_id = auth.uid()`), sin exponer filas de otras marcas; sin políticas de escritura.
- Denegación por defecto para toda otra operación y rol: `anon` no obtiene ninguna política (cero filas vía Data API) y no existen políticas `INSERT`/`UPDATE`/`DELETE` para nadie, porque RLS no puede expresar las invariantes de dominio (versionado, workflow, claim atómico de sync): la única vía de escritura sigue siendo FastAPI con su conexión propietaria/servicio (dueño de las tablas, que no está sujeto a RLS sin `FORCE`).
- El mapeo `auth.uid() = profiles.id` queda documentado como contrato de identidad: el `sub` del JWT de Supabase ya es la PK de `profiles` (lo verifica `app/identity/auth.py`); las políticas dependen de ese contrato.
- Alineación de ledger de migraciones: Alembic sigue siendo la única fuente de verdad del esquema (el ledger de migraciones de Supabase está vacío y se mantiene sin usar); antes de aplicar en producción se inspecciona `alembic_version` y, si el esquema preexistente aplicado fuera de Alembic (consola/MCP) no tiene ledger coincidente, NO se estampa a ciegas: primero se ejecuta un gate de paridad que verifica el esquema aplicado contra la cadena Alembic 001–006 con evidencia concreta (columnas con tipo y nullabilidad, valores y orden de los enums, índices con su definición exacta —incluidos los parciales— y nombres de constraints, incluido el FK truncado por el límite de 63 caracteres de PostgreSQL `fk_brand_knowledge_chunks_brand_dna_version_id_brand_dn_026c`); cualquier diferencia detiene el estampado (alto seguro con diferencia y remediación documentadas) y solo con paridad exacta se estampa `c4a9b2e6f8d1` (vía directa con Alembic, preferida; vía Supabase MCP documentada) antes de avanzar a la cabeza RLS, sin reproducir el DDL ya existente; la migración RLS es idempotente (`DROP POLICY IF EXISTS` + `CREATE POLICY`, `ENABLE ROW LEVEL SECURITY` es idempotente) y su downgrade elimina políticas y deshabilita RLS.
- Sin cambios de código de aplicación ni frontend: antes de aplicar se verifica el propietario real de las tablas y el rol de conexión de la aplicación — la condición de bypass de RLS sin `FORCE` se comprueba, no se asume —, con alto seguro y remediación documentada si no coinciden, y tras aplicar se registra evidencia de lectura y escritura con ese rol; la autorización membership + rol (incluidas mutaciones solo-Creator) queda intacta y sigue siendo la autoridad; RLS es defensa en profundidad del Data API, no un duplicado de las reglas de negocio.

## Capabilities

### New Capabilities
- `database-rls-hardening`: RLS denegación-por-defecto sobre las tablas de dominio en PostgreSQL (Supabase) con políticas de lectura limitadas por membresía vía `auth.uid() = profiles.id`, escrituras exclusivas de la conexión de aplicación, y gestión del esquema solo vía Alembic.

### Modified Capabilities

- Ninguna (no cambia requirements de Brand DNA, Knowledge ni Identity: la autorización del backend y sus contratos HTTP permanecen iguales).

## Impact

- `apps/api/alembic/versions/`: una migración nueva (`down_revision = c4a9b2e6f8d1`) con rama por dialecto.
- `apps/api/tests/`: nuevo `tests/test_rls_migration_sql.py` (verificación offline de la rama PostgreSQL de la migración, sin red ni instancia) y test de contrato de identidad `auth.uid() = profiles.id`; ningún archivo de aplicación cambia.
- Producción (Supabase): tras aplicar, la Data API `anon` no devuelve filas y `authenticated` solo ve marcas/membresías/versiones/chunks de marcas donde es miembro; las escrituras vía Data API quedan imposibles; la verificación en vivo registra evidencia del gate de paridad previo al estampado, de grants (`information_schema.role_table_grants` o `has_table_privilege`, incluida la ausencia explícita de `TRUNCATE` para `anon`/`authenticated`) y de lectura/escritura con el rol de la aplicación; el aislamiento `authenticated` se prueba con un contexto de claims JWT válido (`sub` real) para que `auth.uid()` no sea NULL y las cero filas de un no-miembro sean decisión de política, no un artefacto de contexto vacío.
- `service_role`/conexión propietaria de FastAPI: sin cambios (bypass de RLS); se documenta que `service_role` nunca debe exponerse al cliente.
- Sin dependencias nuevas, sin cambios de API HTTP, sin frontend, sin seeds.
- Riesgo residual acotado: si `profiles.id` dejara de coincidir con `auth.uid()`, las políticas de lectura no devolverían filas (fallo cerrado, no fuga); el contrato queda verificado en tasks.
