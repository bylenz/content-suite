## 1. Endpoints

- [x] 1.1 `GET /creative-items/pipeline?brand_id`: `GROUP BY workflow_status COUNT(*)` scoped por membresía, incluye los 7 estados con cero explícito; verificar con tests que cubran una marca con items en varios estados y una marca vacía.
- [x] 1.2 Membresía-primero en el endpoint de pipeline: 403 sin membresía en `brand_id`; verificar con test dedicado.
- [x] 1.3 `GET /activity?brand_id&limit&offset`: fusiona `workflow_events` de la marca con un evento derivado por cada `brand_dna_versions.published_at` no nulo de la marca, orden cronológico descendente, `limit` 1-50 (default 20) + `offset` + `total`; verificar con tests de fusión, orden y paginación (mismo patrón que `tests/test_trace_facade.py`).
- [x] 1.4 Membresía-primero en el endpoint de actividad: 403 sin membresía en `brand_id`; verificar con test dedicado.

## 2. Frontend

- [x] 2.1 Reemplazar el `FutureCard` de Content Pipeline por el widget real en `DashboardPage.tsx` (y las variantes de Content Reviewer / Visual Compliance Reviewer), consumiendo el desglose de 7 estados y resaltando el subconjunto relevante por rol; verificar manualmente en el navegador para cada rol.
- [x] 2.2 Reemplazar el `FutureCard` de Recent Activity por el widget real, consumiendo el feed paginado; verificar manualmente en el navegador, incluido el estado vacío (marca sin items ni eventos).

## 3. Cierre

- [x] 3.1 Ejecutar la suite completa (`uv run pytest`, `npm run test --workspace @content-suite/web`) y `openspec validate 014-dashboard-activity --strict` antes de considerar la change lista para archivar.
