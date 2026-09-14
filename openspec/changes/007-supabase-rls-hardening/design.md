## Context

Ver `proposal.md`. Producción es Supabase (ADR-002); ADR-003 fija "Supabase autentica, FastAPI autoriza": `app/identity/auth.py` verifica el JWT, toma `sub` como identidad y los servicios resuelven membresía/rol server-side (`app/identity/repository.get_membership`, `authorize_brand_action`). `AuthenticatedUser.id` es el `sub` del token y las consultas lo usan como PK de `profiles` — ese es el contrato `auth.uid() = profiles.id` sobre el que descansan las políticas. La Data API (PostgREST) está expuesta por defecto con las claves `anon`/`authenticated`; el preflight de producción detectó las cinco tablas en `public` sin RLS. El esquema vive únicamente en la cadena Alembic (`dec022b4c864 → b7d1e4c2a9f3 → c4a9b2e6f8d1`); el ledger de migraciones de Supabase está vacío y el esquema de producción se aplicó por fuera de Alembic (consola/MCP), de modo que `alembic_version` puede no existir o no coincidir con el estado real: toda aplicación en producción inspecciona y reconcilia el ledger antes de ejecutar `upgrade` (ver «Reconciliación del ledger en producción»). Dev/test corren SQLite in-memory (`Base.metadata.create_all`), donde RLS no existe.

## Goals / Non-Goals

**Goals:**

- Migración Alembic única, reversible e idempotente que habilita RLS y crea las políticas de lectura acotadas por membresía, aplicable al final de la cadena existente.
- Denegación por defecto para la Data API: `anon` sin filas, `authenticated` solo lectura limitada por membresía, escrituras imposibles vía Data API.
- Cero cambios de aplicación: FastAPI sigue operando sin cambios; que su conexión sea dueña de las tablas (bypass de RLS sin `FORCE`) se verifica antes de aplicar — no se asume —, con alto seguro ante desajuste y evidencia de lectura/escritura post-aplicación.
- Verificación offline reproducible en CI (compilación/inspección de la rama PostgreSQL de la migración, siguiendo el patrón `test_knowledge_postgres_sql.py` de 006).

**Non-Goals:**

- No replica en RLS las reglas de mutación (Creator-only writes, versionado, workflow): RLS no puede expresar invariantes de dominio y duplicarlas crearía una segunda autoridad (ADR-003).
- No usa `FORCE ROW LEVEL SECURITY` (rompería la conexión propietaria de la aplicación sin beneficio: el dueño es la propia API).
- No añade tablas/columnas, no cambia endpoints, seeds, frontend ni dependencias.
- No adopta el ledger de Supabase ni crea `supabase/migrations`: Alembic permanece como fuente única de DDL.
- No endurece tablas futuras (assets, creative, governance): cada change que añada tablas PostgreSQL incluirá su propio RLS; esta change documenta el patrón a seguir.

## Decisions

### Migración Alembic con rama por dialecto (espejo del patrón 006)

Nueva revisión `down_revision = "c4a9b2e6f8d1"` en `apps/api/alembic/versions/`. Rama PostgreSQL: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` para las cinco tablas + `DROP POLICY IF EXISTS` / `CREATE POLICY` para las cinco políticas de lectura. Rama SQLite: `pass` explícito con comentario (RLS no existe; dev/test no cambian). Es exactamente el patrón de dialecto ya aceptado en `c4a9b2e6f8d1` para `vector`, con la misma honestidad documentada.

Alternativa descartada: SQL ad-hoc vía MCP/consola. Invisible para el grafo Alembic, irreproducible en entornos nuevos y rompería `alembic upgrade head` desde cero.

### Políticas exactas

```sql
ALTER TABLE profiles              ENABLE ROW LEVEL SECURITY;
ALTER TABLE brands                ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_memberships     ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_dna_versions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_knowledge_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_profiles_select_self ON profiles;
CREATE POLICY rls_profiles_select_self ON profiles FOR SELECT TO authenticated
  USING (id = auth.uid());

DROP POLICY IF EXISTS rls_brand_memberships_select_own ON brand_memberships;
CREATE POLICY rls_brand_memberships_select_own ON brand_memberships FOR SELECT TO authenticated
  USING (profile_id = auth.uid());

DROP POLICY IF EXISTS rls_brands_select_members ON brands;
CREATE POLICY rls_brands_select_members ON brands FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM brand_memberships m
                 WHERE m.profile_id = auth.uid() AND m.brand_id = brands.id));

DROP POLICY IF EXISTS rls_brand_dna_versions_select_members ON brand_dna_versions;
CREATE POLICY rls_brand_dna_versions_select_members ON brand_dna_versions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM brand_memberships m
                 WHERE m.profile_id = auth.uid() AND m.brand_id = brand_dna_versions.brand_id));

DROP POLICY IF EXISTS rls_brand_knowledge_chunks_select_members ON brand_knowledge_chunks;
CREATE POLICY rls_brand_knowledge_chunks_select_members ON brand_knowledge_chunks FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM brand_memberships m
                 WHERE m.profile_id = auth.uid() AND m.brand_id = brand_knowledge_chunks.brand_id));
```

Razones:

- **`TO authenticated` explícito**: `anon` queda sin política alguna → cero filas (denegación por defecto de RLS). Sin `TO`, la política aplicaría a `PUBLIC` y abriría `anon`.
- **Auto-membresía sin recursión**: el `EXISTS` de las políticas de marca filtra por `profile_id = auth.uid()`, exactamente las filas que `rls_brand_memberships_select_own` permite ver; la subconsulta de política se evalúa con los permisos del usuario que consulta, así que la composición cierra sin ciclos ni `SECURITY DEFINER`. El invariante anti-recursión queda explícito: ninguna política referencia en su `USING` la tabla que protege y las políticas de marca referencian únicamente `brand_memberships` (cuya política no referencia tablas de dominio) → grafo de referencias acíclico; se afirma con una aserción dedicada en el test offline (tarea 2.1), además del pin exacto de la secuencia.
- **`USING` sin `WITH CHECK`**: solo `FOR SELECT`; no hay políticas de escritura que revisar.
- **Sin escrituras vía Data API**: cualquier `INSERT/UPDATE/DELETE` de `authenticated`/`anon` queda rechazado por ausencia de política. Las mutaciones solo-Creator (draft/publish/sync) permanecen donde ya están validadas: FastAPI.
- **Nombres `rls_<tabla>_<op>_<alcance>`**: descubribles con `source-named` policies y sin colisión con los prefijos existentes (`pk_`, `fk_`, `uq_`, `ix_`).

Alternativa descartada: políticas Creator-gated de escritura en RLS. Duplicaría la autorización del backend en una segunda superficie que no puede expresar "no sobrescribir versiones publicadas" ni el claim atómico de sync — un bypass estructural de las invariantes de dominio con apariencia de seguridad. La denegación total de escrituras es más segura y más simple.

Alternativa descartada: view por marca o `SECURITY DEFINER` helper para el check de membresía. Más objetos, más superficie, mismo resultado que el `EXISTS` con auto-membresía.

### Downgrade

`DROP POLICY IF EXISTS` de las cinco políticas + `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` (PostgreSQL); no-op en SQLite. No se toca `auth.uid()` ni el esquema `auth` (objeto de Supabase, compartido).

### Calificación de esquema en las referencias de las políticas

Decisión: se mantienen **sin calificar** las referencias a `brand_memberships` en los predicados `EXISTS` (idéntico a la implementación `597b7798962f` y a sus tests offline, que pinean la secuencia literal). No es necesario escribir `public.brand_memberships`: PostgreSQL analiza la expresión al ejecutar `CREATE POLICY` y persiste el árbol con los OIDs de las relaciones ya resueltos; en ejecución no hay re-resolución vía `search_path`, por lo que la calificación no cambia comportamiento ni añade endurecimiento real. Calificar exigiría tocar migración y tests sin ganancia (y esta change no replica DDL ya aplicado en producción).

Techo deliberado: si en el futuro se generaran políticas dinámicamente bajo un `search_path` no controlado (DDL programático con nombres no verificables en creación), la calificación explícita pasaría a ser obligatoria; la regla queda documentada aquí para esa eventualidad.

### Idempotencia y ledger

`ENABLE/DISABLE ROW LEVEL SECURITY` son idempotentes y cada `CREATE POLICY` va precedido de su `DROP POLICY IF EXISTS`: re-ejecutar las sentencias manualmente (p. ej. tras un despliegue interrumpido) converge al mismo estado sin errores de objeto duplicado. El versionado de la migración lo lleva `alembic_version`, único ledger del esquema; el ledger de Supabase permanece vacío y sin usar. El contrato con Supabase es solo de plataforma: `auth.uid()` ya existe en el proyecto (Auth activo) y las tablas ya viven en `public`.

### Reconciliación del ledger en producción (`alembic_version`)

Paso previo obligatorio antes de cualquier `upgrade` en producción: inspeccionar `SELECT version_num FROM alembic_version` (la tabla puede no existir). Casos:

- **Tabla ausente o vacía con las cinco tablas de dominio ya presentes** (esquema `c4a9b2e6f8d1` aplicado fuera de Alembic): ejecutar primero el gate de paridad de esquema (ver «Verificación de paridad de esquema»); solo con paridad exacta, estampar `c4a9b2e6f8d1` sin ejecutar migraciones y luego `upgrade head` corre únicamente la revisión RLS. El estampado nunca reproduce DDL existente.
- **Fila existente distinta de la cabeza esperada**: alto y diagnóstico manual; no se estampa a ciegas (riesgo de saltar o duplicar DDL).
- **Fila = `c4a9b2e6f8d1`**: continuar directo al `upgrade`.

### Verificación de paridad de esquema (gate obligatorio antes de estampar)

El esquema de producción se aplicó fuera de Alembic (consola/MCP): la evidencia de paridad concreta contra la cadena Alembic 001–006 es obligatoria (MUST) antes de estampar `c4a9b2e6f8d1`, y se recoge consultando catálogo (sin DDL):

- **Columnas** (tipo, nullabilidad, defaults) de las cinco tablas:

```sql
SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('brands','profiles','brand_memberships','brand_dna_versions','brand_knowledge_chunks')
ORDER BY table_name, ordinal_position;
```

- **Enums** con valores y orden esperados: `brand_role` = `CREATOR, CONTENT_REVIEWER, VISUAL_REVIEWER`; `brand_dna_status` = `DRAFT, ACTIVE, ARCHIVED`; `brand_dna_knowledge_status` = `NOT_SYNCED, SYNCING, SYNCED, OUTDATED, FAILED`; `knowledge_scope` = `TEXT, VISUAL, BOTH`:

```sql
SELECT t.typname, e.enumsortorder, e.enumlabel
FROM pg_enum e
JOIN pg_type t ON t.oid = e.enumtypid
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'public'
ORDER BY t.typname, e.enumsortorder;
```

- **Índices** con nombre y definición exacta (incluidos los `WHERE` de los parciales `uq_brand_dna_versions_draft_per_brand`, `uq_brand_dna_versions_active_per_brand` e `ix_brand_knowledge_chunks_mandatory_per_version`):

```sql
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('brands','profiles','brand_memberships','brand_dna_versions','brand_knowledge_chunks')
ORDER BY tablename, indexname;
```

- **Constraints** con nombre exacto (los `pk_`/`uq_`/`fk_` de la cadena). En particular, el FK cuyo nombre lógico tiene 65 caracteres existe en PostgreSQL truncado por el límite de 63 con la regla de SQLAlchemy `left(name,55) || '_' || right(md5(name),4)`:

```sql
SELECT conrelid::regclass AS table_name, conname, contype
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY conrelid::regclass::text, conname;
```

  Esperado (nombre truncado, sufijo md5 del nombre lógico completo): `fk_brand_knowledge_chunks_brand_dna_version_id_brand_dn_026c`.

- **Vector**: extensión `vector` instalada y columna `embedding` de tipo `vector` sin dimensión fija (`atttypmod = -1`):

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute
WHERE attrelid = 'public.brand_knowledge_chunks'::regclass AND attname = 'embedding';
```

**Regla de alto seguro**: cualquier diferencia contra la cadena (columna, índice o constraint faltante o extra; tipo o nullabilidad distintos; valor de enum faltante o en otro orden; nombre de constraint divergente —incluido el FK truncado—; `embedding` con tipmod) detiene el estampado y el `upgrade`: se documenta la diferencia y la remediación (alinear el DDL de producción a la cadena o corregir la cadena por change) antes de reintentar. Nunca se estampa a ciegas.

Vías soportadas (ambas seguras; ninguna reproduce el DDL ya aplicado):

- **Directa con Alembic (preferida)**: `CONTENT_SUITE_DATABASE_URL` apuntando a Supabase por la conexión directa o pooler de sesión (el pooler en modo transacción rompe las sesiones de Alembic); `uv run alembic current` inspecciona, `uv run alembic stamp c4a9b2e6f8d1` estampa, `uv run alembic upgrade head` avanza solo la revisión nueva y actualiza el ledger en la misma transacción.
- **Vía Supabase MCP**: cuando no hay conexión directa; inspección con el mismo SQL; estampado creando `alembic_version` con el esquema exacto de Alembic (`CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))` + `INSERT`) con `'c4a9b2e6f8d1'`; si el DDL de la revisión RLS se ejecuta por MCP, MUST avanzar `alembic_version` a la nueva revisión en la misma operación — si no, el ledger queda desincronizado.

Alternativa descartada: `upgrade head` sobre una base sin ledger coincidente. Alembic intentaría reproducir desde `dec022b4c864` y fallaría contra objetos ya existentes (o, en una base vacía, crearía un esquema paralelo).

### Verificación de propietario y rol de conexión (pre y post aplicación)

Pre-aplicación (obligatoria, antes de cualquier DDL RLS): consultar el propietario real de las tablas y el rol real de la conexión de la aplicación:

```sql
SELECT tablename, tableowner FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('brands','profiles','brand_memberships','brand_dna_versions','brand_knowledge_chunks');
```

y el rol con el que conecta la aplicación (`SELECT current_user, current_role;` ejecutado en esa conexión: usuario del `CONTENT_SUITE_DATABASE_URL` o del pooler). Regla de decisión: si el rol de la aplicación no es el propietario de las tablas, habilitar RLS rompería el backend (quedaría sujeto a políticas de solo lectura) → **alto seguro**: no se aplica DDL y se documenta la remediación (reconectar la aplicación con el rol propietario/`service_role` de servidor o transferir la propiedad), decisión de plataforma registrada antes de reintentar. El bypass del dueño no se asume: se verifica.

Post-aplicación (evidencia): con el rol de la aplicación, probar lectura y escritura (p. ej. `BEGIN; SELECT count(*) FROM brands; <INSERT/UPDATE de prueba>; ROLLBACK;` o un flujo real de la API observado) y registrar el resultado como evidencia del bypass. Además, evidencia de grants sobre las cinco tablas:

```sql
SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('brands','profiles','brand_memberships','brand_dna_versions','brand_knowledge_chunks');
```

(o `has_table_privilege('<rol>', '<tabla>', '<privilegio>')`) documentando qué privilegios reales tienen `anon`, `authenticated` y el rol de la aplicación tras el hardening. Además del listado, se registra explícitamente la ausencia de `TRUNCATE` para `anon` y `authenticated`: RLS no gobierna `TRUNCATE` (operación a nivel de tabla regida por grants, invisible para las políticas), por lo que su ausencia se verifica por grants, p. ej. (repetido por tabla):

```sql
SELECT has_table_privilege('anon', 'public.brands', 'TRUNCATE') AS anon_truncate,
       has_table_privilege('authenticated', 'public.brands', 'TRUNCATE') AS authenticated_truncate;
```

con resultado esperado `false` para ambos roles en las cinco tablas.

### Verificación offline (patrón 006)

`tests/test_rls_migration_sql.py` compila/inspecciona la rama PostgreSQL de la migración sin red ni instancia: afirma que las cinco tablas habilitan RLS, que las cinco políticas existen con `TO authenticated` y su predicado de membresía correcto, que no existe ninguna política `FOR INSERT/UPDATE/DELETE`, que ninguna política omite `TO authenticated`, el invariante anti-recursión (ninguna política referencia la tabla que protege; las de marca solo `brand_memberships` — grafo acíclico) y que la rama SQLite es no-op. Además, un test de contrato de identidad verifica que `AuthenticatedUser.id` sigue siendo el `sub` verificado del JWT (el mapeo del que dependen las políticas). `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` en SQLite valida reversibilidad local.

## Risks / Trade-offs

- [La lectura vía Data API permite a un miembro ver chunks/versiones de su marca sin pasar por la API] → Aceptado deliberadamente: son exactamente los mismos datos que el backend ya le sirve por membresía (los tres roles leen); no expone borradores ajenos ni datos de otras marcas. La superficie de escritura —donde vive el riesgo real— queda cerrada.
- [`profiles.id` deja de coincidir con `auth.uid()` (p. ej. seeds con UUID propios)] → Fallo cerrado: las políticas no devuelven filas; la API no se ve afectada. El contrato queda afirmado por test y documentado en `.env.example`/README solo si ya existe esa documentación de seeds; si no, se registra en la tarea de verificación.
- [`service_role` bypassa RLS y expuesto al cliente anularía todo] → Fuera de alcance técnico de una migración: se documenta en la migración que es secreto de servidor; su gestión es de plataforma, no de esquema.
- [Tablas futuras creadas sin RLS] → Mitigado por patrón documentado aquí + revisión por change (Non-Goal explícito de cubrirlas ahora).
- [Costo de los `EXISTS` por fila en scans amplios vía Data API] → Irrelevante a esta escala (decenas de filas por marca, índice `ix_brand_knowledge_chunks_brand_version` ya existe); revisitado solo si aparece un consumidor real de Data API.
- [El rol real de conexión de la aplicación no es el propietario de las tablas] → Detención explícita en la verificación pre-aplicación (alto + remediación documentada) en lugar de asumir el bypass del dueño; sin backend roto ni hardening parcial.
- [`alembic_version` ausente o desincronizado en producción, o drift entre el esquema MCP-aplicado y la cadena] → El procedimiento inspecciona, ejecuta el gate de paridad de esquema y solo con paridad exacta estampa; el estampado no ejecuta migraciones y ninguna vía soportada reproduce el DDL ya aplicado; cualquier diferencia detiene el despliegue con remediación documentada.

## Migration Plan

1. **Validación offline previa al DDL de producción** (precondición): `ruff`, `ty`, `pytest`, round-trip `alembic` en SQLite, `npx @fission-ai/openspec@latest validate 007-supabase-rls-hardening --strict` y `git diff --check` — todo MUST pasar antes de tocar producción (orden de tareas 3.1 → 3.2 → 3.3).
2. **Pre-aplicación en producción**: (a) reconciliación de `alembic_version` según «Reconciliación del ledger en producción» (inspección → **gate de paridad de esquema** → estampado seguro de `c4a9b2e6f8d1` solo con paridad exacta si el esquema preexistente carece de ledger coincidente; vía directa con Alembic preferida, vía MCP documentada); (b) verificación de propietario y rol de conexión según «Verificación de propietario y rol de conexión», con alto seguro y remediación documentada ante cualquier desajuste.
3. **Aplicación**: `uv run alembic upgrade head` con `CONTENT_SUITE_DATABASE_URL` de Supabase (o DDL vía MCP avanzando `alembic_version` a la nueva revisión en la misma operación); solo la revisión RLS debe ejecutarse.
4. **Verificación post-aplicación en Supabase**: catálogo (`pg_tables.relrowsecurity`, `pg_policies`) confirma RLS + cinco políticas; evidencia de grants (`information_schema.role_table_grants`/`has_table_privilege`) incluida la ausencia explícita de `TRUNCATE` para `anon`/`authenticated` en las cinco tablas; denegación/aislamiento leyendo como `authenticated` con un contexto de claims JWT válido (`SET LOCAL ROLE authenticated; SET LOCAL request.jwt.claims = '{"sub":"<profile_id real>","role":"authenticated"}'` en transacción con `ROLLBACK`, o equivalente soportado por el cliente SQL disponible) para que `auth.uid()` no sea NULL — sin claims válidos, cero filas sería un resultado vacuo, no evidencia —, comprobando: un `sub` con membresía ve únicamente filas de su(s) marca(s) (>0), un `sub` sin membresía ve 0 filas por decisión de política, y `anon` ve 0 filas; evidencia de lectura/escritura con el rol de la aplicación. La tarea de verificación manual registra los pasos exactos y la evidencia.
5. **Rollback**: `uv run alembic downgrade -1` elimina políticas y deshabilita RLS.

No hay ventana de coordenación con la aplicación: sujeto a la verificación pre-aplicación de propietario/rol (el backend conecta como dueño, sin `FORCE`), la migración puede aplicarse en caliente sin cambios de código ni reinicios.
