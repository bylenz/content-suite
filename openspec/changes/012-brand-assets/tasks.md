## 0. Precondición

- [x] 0.1 Confirmar que `private-storage` (008-visual-compliance) tiene un adapter real (`app/storage/providers/...` o equivalente) antes de iniciar 2.x/3.x; si no lo tiene, implementarlo primero como parte de 008 — no duplicarlo dentro de esta change.

## 1. Migración y modelo

- [x] 1.1 Migración Alembic para `brand_assets` (`id`, `brand_id` FK, `brand_dna_version_id` FK nullable, `type` enum `PRIMARY_LOGO|ALT_LOGO|VISUAL_REFERENCE`, `storage_path`, `metadata` jsonb, `created_at`), con índice por `brand_id`; habilitar RLS y política de lectura por membresía en la misma migración (no diferirlo como quedó diferido para `creative_items`); verificar con `uv run alembic upgrade head` sobre SQLite y con un test offline de las sentencias PostgreSQL (mismo patrón que `test_rls_hardening_extension_sql.py`).
- [x] 1.2 Modelo SQLAlchemy `BrandAsset` + repository (get/list/create/delete) en el módulo del dominio (`app/brand_dna/` o `app/brand_assets/`, decidir por cercanía al resto del código de Brand DNA); verificar con un test de modelo/repositorio directo sobre SQLite.

## 2. Endpoints

- [x] 2.1 `POST /brands/{brand_id}/assets` (multipart: `type`, archivo): CREATOR con membresía, valida vía `private-storage`, reemplaza en la misma transacción si `type` es `PRIMARY_LOGO`/`ALT_LOGO` y ya existe uno, captura `brand_dna_version_id` activo; verificar con tests de creación, reemplazo, y rechazo de archivo inválido.
- [x] 2.2 `GET /brands/{brand_id}/assets`: cualquier miembro con membresía, cada asset con signed URL vigente; verificar con tests de lectura por cada rol y de 403 sin membresía.
- [x] 2.3 `DELETE /brands/{brand_id}/assets/{asset_id}`: CREATOR con membresía, 404 para asset inexistente/ajeno/sin membresía; verificar con tests de eliminación y los tres casos 404.

## 3. Consumo cruzado

- [x] 3.1 Wiring de lectura desde `visual-compliance`: el flujo de auditoría multimodal puede resolver el `PRIMARY_LOGO` de la marca como contexto de comparación vía este mismo listado/lectura; verificar con un test de integración que confirme que `visual-compliance` no reimplementa su propio acceso a storage para esto.

## 4. Frontend

- [x] 4.1 Sección de Brand Assets en `apps/web/src/features/brand-dna/` (3 slots: Primary Logo, Alternative Logo, Visual References — subir/reemplazar/eliminar), acorde a `starter-design/Content Suite.dc.html`; verificar manualmente en el navegador y con tests de componente para los tres flujos (subir, reemplazar, eliminar).

## 5. Cierre

- [x] 5.1 Ejecutar la suite completa y `openspec validate 012-brand-assets --strict` antes de considerar la change lista para archivar.
