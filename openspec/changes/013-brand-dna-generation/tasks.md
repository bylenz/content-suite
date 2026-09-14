## 1. AI Platform

- [x] 1.1 Mover `BrandDnaDocument` (identity/voice/communication/visual_rules/restrictions, límites de tamaño existentes) de `app/brand_dna/schemas.py` a `app/ai/contracts.py`; actualizar el import en `brand_dna/schemas.py`; verificar que `uv run pytest tests/test_brand_dna_*.py` sigue pasando sin cambios de comportamiento.
- [x] 1.2 Ampliar `ContractT` en `app/ai/runner.py` y el `Literal` de `TraceSummary.contract` con el contrato de Brand DNA; agregar la rama en `build_trace_summary`; verificar con `uv run pytest tests/test_ai_contracts.py tests/test_ai_runner.py`.
- [x] 1.3 Activar el prompt `brand.architect.v1` ya registrado (confirmar que su texto sigue siendo correcto para el contrato movido); verificar con `uv run pytest tests/test_ai_prompts.py`.

## 2. Persistencia

- [x] 2.1 Migración Alembic: columna `brief` (jsonb, nullable) en `brand_dna_versions`; verificar con `uv run alembic upgrade head` y un test offline de la migración.
- [x] 2.2 Definir el schema de brief de entrada (`BrandBriefIn`: datos básicos, audiencia, personalidad/tono, reglas siempre/nunca — acorde a `starter-design/Content Suite.dc.html`); verificar con un test de validación estricta.

## 3. Endpoint y servicio

- [x] 3.1 `POST /brands/{brand_id}/brand-dna/generate`: CREATOR con membresía, invoca `run_capability` con el prompt de generación, persiste vía `_apply_draft_upsert` + guarda `brief`; verificar con tests de creación sobre marca sin Brand DNA y de reemplazo sobre un DRAFT existente.
- [x] 3.2 Falla segura: 503 sin proveedor configurado, nada persiste con salida inválida; verificar con tests espejo de `test_creative_ai.py::test_generate_503_when_text_provider_unconfigured` / `::test_generate_with_invalid_structured_output_persists_nothing`.
- [x] 3.3 Confirmar que la generación NO evalúa `knowledge_status` de ninguna versión; verificar con un test que genera sobre una marca cuya ACTIVE (si existe) está `OUTDATED` o `NOT_SYNCED` y confirma que procede igual.
- [x] 3.4 Confirmar el efecto ya existente de `_apply_draft_upsert` (marcar ACTIVE `OUTDATED` si estaba `SYNCED`) sigue aplicando también en el camino de generación; verificar con un test dedicado.

## 4. Frontend

- [x] 4.1 Pantalla de brief de onboarding (Brand Basics, Audience, Personality & Tone, Brand Rules) en `apps/web/src/features/brand-dna/`, acorde a `starter-design/Content Suite.dc.html`, con acción "Generate Brand DNA" hacia el nuevo endpoint y aterrizaje en el DRAFT generado para revisión humana; verificar manualmente en el navegador.

## 5. Cierre

- [x] 5.1 Ejecutar la suite completa (`uv run pytest`) y `openspec validate 013-brand-dna-generation --strict` antes de considerar la change lista para archivar.
