## Purpose

Blinda las tablas de dominio en PostgreSQL (Supabase) con Row Level Security de denegación por defecto, de modo que la Supabase Data API solo exponga lecturas acotadas por membresía de marca y ninguna escritura, dejando la autorización de negocio en FastAPI.

## ADDED Requirements

### Requirement: RLS habilitado con denegación por defecto en las tablas de dominio
Las tablas `brands`, `profiles`, `brand_memberships`, `brand_dna_versions` y `brand_knowledge_chunks` MUST tener Row Level Security habilitado en el esquema `public` de PostgreSQL (Supabase) en todo momento después de aplicar la migración. El rol `anon` de la Data API MUST NOT recibir ninguna política: cualquier consulta anónima sobre dichas tablas devolverá cero filas y cualquier intento de escritura será rechazado. Ninguna política podrá otorgar acceso que el backend no concedería (roles de cliente nunca son fuente de autorización).

#### Scenario: Consulta anónima vía Data API
- **WHEN** un cliente sin sesión consulta cualquiera de las cinco tablas a través de la Data API con la clave `anon`
- **THEN** la respuesta no contiene filas ni permite escrituras

#### Scenario: RLS ausente en una tabla de dominio
- **WHEN** se audita el estado de RLS tras aplicar la migración
- **THEN** las cinco tablas reportan RLS habilitado; ninguna queda desprotegida

#### Scenario: Evidencia de grants en la auditoría
- **WHEN** se auditan los privilegios reales tras aplicar la migración
- **THEN** la evidencia de grants (`information_schema.role_table_grants` o `has_table_privilege`) sobre las cinco tablas queda registrada para `anon`, `authenticated` y el rol de la aplicación, y registra explícitamente que ni `anon` ni `authenticated` tienen privilegio `TRUNCATE` en ninguna de las cinco tablas (RLS no gobierna `TRUNCATE`; solo los grants lo hacen)

### Requirement: Lecturas autenticadas acotadas por membresía de marca
Las políticas de lectura para usuarios autenticados (`authenticated`) SHALL derivar la identidad desde `auth.uid()` y su mapeo con `profiles.id` (contrato de identidad: el `sub` del JWT de Supabase es la PK de `profiles`), nunca desde datos enviados por el cliente. Un usuario autenticado solo podrá: leer su propia fila en `profiles`; leer sus propias filas en `brand_memberships` (`auth.uid() = profile_id`); y leer en `brands`, `brand_dna_versions` y `brand_knowledge_chunks` únicamente filas de marcas donde tiene membresía, verificada con `EXISTS` sobre `brand_memberships` con `profile_id = auth.uid()`. Las filas de marcas ajenas MUST NOT ser visibles vía Data API para ningún rol demo (`CREATOR`, `CONTENT_REVIEWER`, `VISUAL_REVIEWER`): los tres roles leen lo mismo que el backend les permite leer por membresía. Las políticas de lectura MUST mantener un grafo de referencias acíclico: ninguna referencia en su predicado a la tabla que protege, y las políticas de marca referencian únicamente `brand_memberships` (sin auto-referencia ni recursión infinita de RLS).

#### Scenario: Miembro lee su marca
- **WHEN** un usuario autenticado con membresía en la marca consulta `brands`, `brand_dna_versions` o `brand_knowledge_chunks` vía Data API
- **THEN** solo recibe filas de marcas donde es miembro

#### Scenario: No miembro no lee marcas ajenas
- **WHEN** un usuario autenticado sin membresía en una marca consulta esas tablas
- **THEN** las filas de esa marca no aparecen en la respuesta

#### Scenario: Membresías y perfil propios
- **WHEN** un usuario autenticado consulta `brand_memberships` y `profiles` vía Data API
- **THEN** solo ve sus propias membresías y su propia fila de perfil

#### Scenario: Contrato de identidad roto
- **WHEN** no existe fila en `profiles` con `id = auth.uid()` de un usuario autenticado
- **THEN** ese usuario no ve filas de marcas ni membresías vía Data API (fallo cerrado, sin fuga)

#### Scenario: Aislamiento verificado con claims JWT válidos
- **WHEN** se verifica el acceso de `authenticated` a las tablas de dominio (Data API o SQL de prueba)
- **THEN** la verificación usa un contexto de claims JWT válido con un `sub` real, de modo que `auth.uid()` no sea NULL y las cero filas de un no-miembro sean decisión de política, no un artefacto de contexto vacío

#### Scenario: Sin auto-referencia en las políticas
- **WHEN** se auditan los predicados de las políticas creadas (p. ej. `pg_policies`)
- **THEN** ninguna política referencia la tabla que protege y las de marca referencian solo `brand_memberships`: no existe recursión infinita de RLS

### Requirement: Escrituras exclusivas de la conexión de aplicación
No existirán políticas `INSERT`, `UPDATE` ni `DELETE` para ningún rol de la Data API sobre las cinco tablas: la única vía de escritura SHALL ser la conexión propietaria de la aplicación FastAPI, cuyo rol de conexión MUST verificarse como dueño de las tablas antes de habilitar RLS (el dueño no está sujeto a RLS sin `FORCE`; la condición se verifica, no se asume), y que ya aplica autorización de dominio (membresía, rol `CREATOR` para mutaciones de Brand DNA/Knowledge, versionado e invariantes de workflow). La migración MUST NOT usar `FORCE ROW LEVEL SECURITY` y `service_role` (bypass de RLS en Supabase) MUST permanecer como secreto de servidor jamás expuesto al cliente.

#### Scenario: Escritura vía Data API rechazada
- **WHEN** cualquier usuario autenticado intenta insertar, actualizar o borrar filas de las cinco tablas vía Data API
- **THEN** la operación es rechazada por ausencia de política aplicable

#### Scenario: Backend sigue operando sin cambios
- **WHEN** FastAPI ejecuta sus flujos habituales (draft, publish, sync, lectura) tras habilitar RLS
- **THEN** todas las operaciones de dominio funcionan sin cambios de código ni permisos adicionales

#### Scenario: Verificación pre-aplicación de propietario
- **WHEN** antes de aplicar RLS se consultan el propietario real de las tablas y el rol de conexión de la aplicación
- **THEN** si el rol de la aplicación no es el propietario, el despliegue se detiene sin ejecutar DDL y se documenta la remediación (el bypass del dueño no se asume)

#### Scenario: Evidencia post-aplicación del rol de aplicación
- **WHEN** RLS queda habilitado
- **THEN** se registra evidencia de lectura y escritura exitosas con el rol de conexión de la aplicación (transacción de prueba revertida o flujo real de la API)

### Requirement: Esquema gestionado exclusivamente por la cadena Alembic
El hardening SHALL entregarse como una migración Alembic reversible, idempotente en sus sentencias de políticas (`DROP POLICY IF EXISTS` + `CREATE POLICY`; `ENABLE ROW LEVEL SECURITY` es idempotente), encadenada al final del grafo existente. Alembic es el ledger único del esquema: el ledger de migraciones de Supabase permanece sin usar y el cambio MUST NOT introducir fuentes paralelas de DDL. El dialecto SQLite (dev/test) ejecuta la migración como no-op explícito documentado, sin romper `alembic upgrade head`. Cuando el esquema de producción exista aplicado fuera de Alembic y sin fila coincidente en `alembic_version`, la reconciliación MUST realizarse estampando `c4a9b2e6f8d1` por una vía soportada antes de cualquier `upgrade`, sin reproducir DDL ya aplicado, y ese estampado MUST estar precedido por evidencia de paridad concreta del esquema aplicado contra la cadena Alembic — columnas con su tipo y nullabilidad, valores y orden de los enums, índices y nombres de constraints (incluido el FK truncado por el límite de 63 caracteres de PostgreSQL, `fk_brand_knowledge_chunks_brand_dna_version_id_brand_dn_026c`) —; ante cualquier diferencia, el estampado y el `upgrade` MUST detenerse con la diferencia y su remediación documentadas. El downgrade elimina las políticas creadas y deshabilita RLS en las cinco tablas.

#### Scenario: Aplicación repetida de la migración
- **WHEN** la migración se aplica de nuevo sobre un estado ya endurecido (re-ejecución manual de sus sentencias)
- **THEN** no falla por objetos duplicados y el estado final es idéntico

#### Scenario: Round-trip en SQLite
- **WHEN** se ejecuta `alembic upgrade head` y `alembic downgrade -1` en el entorno SQLite de tests
- **THEN** ambas direcciones completan sin error y el entorno local queda funcional

#### Scenario: Esquema preexistente sin ledger de Alembic
- **WHEN** producción contiene el esquema de `c4a9b2e6f8d1` aplicado fuera de Alembic y sin fila coincidente en `alembic_version`
- **THEN** con paridad exacta verificada contra la cadena (columnas con tipo y nullabilidad, enums, índices, constraints incluido el FK truncado), se estampa `c4a9b2e6f8d1` por una vía soportada antes de avanzar y ningún DDL ya aplicado se reproduce

#### Scenario: Diferencia de esquema detectada antes del estampado
- **WHEN** el gate de paridad detecta cualquier diferencia entre el esquema aplicado en producción y la cadena Alembic (columna, tipo, nullabilidad, valor u orden de enum, índice o nombre de constraint —incluido el FK truncado—)
- **THEN** no se estampa ni se ejecuta `upgrade`: el despliegue se detiene y la diferencia y su remediación quedan documentadas

#### Scenario: Reversibilidad en PostgreSQL
- **WHEN** se hace downgrade de la migración en PostgreSQL (Supabase)
- **THEN** las políticas de lectura desaparecen y RLS queda deshabilitado en las cinco tablas
