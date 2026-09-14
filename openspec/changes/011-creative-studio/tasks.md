## 1. Creación y lectura

- [x] 1.1 Verificar "Creación de creative items" contra `test_creative_items.py::test_creator_creates_draft_item_per_type` (siembra DRAFT + versión 1 HUMAN_EDIT por cada `type`) y `::test_create_rejects_unknown_type_and_extra_fields` (422 en tipo/campo inválido); comando: `uv run pytest tests/test_creative_items.py -q`.
- [x] 1.2 Verificar "Lectura sin fuga de existencia" contra `test_creative_items.py::test_members_list_and_read_items_of_their_brand`, `::test_cross_brand_item_access_answers_404`, `::test_missing_item_answers_404` y `test_creative_versions.py::test_version_detail_rejects_version_of_other_item` / `::test_version_detail_non_member_gets_404`.
- [x] 1.3 Verificar "Escritura restringida a Creator con membresía" contra `test_creative_items.py::test_create_requires_creator_role`, `::test_create_requires_brand_membership` (403 al crear sin membresía), `test_creative_versions.py::test_reviewer_cannot_edit`, `::test_edit_by_non_member_is_404` (nuevo, 404 al editar un item existente sin membresía), `test_creative_ai.py::test_reviewer_cannot_generate`, `::test_generate_by_non_member_is_404` (nuevo). La distinción 403-al-crear vs. 404-en-item-existente viene de leer `app/creative/service.py::create_item` (chequea membership directo, sin `_resolve_item`) vs. `_resolve_item` (404 antes de rol, item y no-miembro indistinguibles) — el hallazgo inicial de la investigación (404 uniforme) era impreciso y se corrigió en `specs/creative-studio/spec.md` antes de cerrar esta tarea.

## 2. Ventana editable y validación

- [x] 2.1 Verificar "Ventana editable y versionado inmutable" contra `test_creative_versions.py::test_edit_while_pending_review_is_rejected`, `::test_versions_are_numbered_monotonically`, `::test_edit_creates_v2_and_v1_stays_intact`, `::test_output_content_type_must_match_item_type`, `::test_explicit_brief_replaces_previous`, y `test_creative_ai.py::test_generate_while_pending_review_is_409` (misma guarda para IA).
- [x] 2.2 Verificar "Validación estricta y límite de tamaño del brief" contra `app/creative/schemas.py` (`_require_brief_size`, `MAX_BRIEF_BYTES = 16 * 1024`), `test_creative_versions.py::test_output_contract_rejects_both_and_neither_body` y `test_creative_items.py::test_create_rejects_brief_over_16kb` (nuevo — no existía cobertura del límite de 16KB; se añadió en vez de dejarlo como deuda).

## 3. Generación IA y consistency-check

- [x] 3.1 Verificar "Generación y regeneración asistida por IA con citas verificadas" contra `test_creative_ai.py::test_generate_creates_ai_version_for_each_type`, `::test_generate_persists_model_cited_rule_when_it_is_real`, `::test_generate_drops_fabricated_rule_ids`, `::test_regenerates_as_new_version_with_regenerated_origin`, `::test_generate_with_invalid_structured_output_persists_nothing`.
- [x] 3.2 Verificar el fail-safe de Brand DNA/proveedor contra `test_creative_ai.py::test_generate_fails_safe_without_synced_knowledge` (parametrizado, incluye `OUTDATED`), `::test_generate_503_without_active_brand_dna`, `::test_generate_503_when_text_provider_unconfigured`.
- [x] 3.3 Verificar "Consistency-check con score calculado en backend" contra `test_creative_ai.py::test_consistency_check_persists_score_without_touching_content`, `::test_consistency_check_without_content_is_422`, `::test_consistency_check_fails_safe_without_knowledge`.

## 4. Contexto aplicado

- [x] 4.1 Verificar "Contexto aplicado siempre relativo a la última versión" contra `test_creative_applied_context.py::test_context_tracks_the_current_version_after_edit`, `::test_context_without_published_dna_has_null_version`, `::test_context_identifies_dna_version_and_rules`, `::test_context_readable_by_reviewers_not_by_other_brand`.

## 5. Cierre

- [x] 5.1 Ejecutar la suite completa de Creative Studio y confirmar 0 fallos: `uv run pytest tests/test_creative_items.py tests/test_creative_submit.py tests/test_creative_versions.py tests/test_creative_ai.py tests/test_creative_applied_context.py -q` → 55 passed (52 preexistentes + 3 añadidas por esta change: `test_create_rejects_brief_over_16kb`, `test_edit_by_non_member_is_404`, `test_generate_by_non_member_is_404`).
- [x] 5.2 Confirmar con `openspec validate 011-creative-studio --strict` que la capability nueva no choca con los requirements ya aceptados de `008-visual-compliance` ni `009-content-governance` (sin overlap de headers de Requirement).
