## Context

`apps/api/app/creative/` y `apps/web/src/features/creative/` ya están implementados y cubiertos por `apps/api/tests/test_creative_items.py`, `test_creative_submit.py`, `test_creative_versions.py`, `test_creative_ai.py` y `test_creative_applied_context.py`. Esta change no diseña nada nuevo: documenta ese comportamiento ya construido y verificado. Ver `proposal.md - Why` para cómo se llegó a este vacío (el número `008` que `009-content-governance` esperaba para esta capability terminó asignado a `visual-compliance`).

## Goals / Non-Goals

**Goals:**
- Dar a Creative Studio una capability formal (`creative-studio`) que documente con precisión su comportamiento ya verificado por tests, para que `content-governance` y `visual-compliance` tengan una base spec'd sobre la cual extender su máquina de estados.
- Trazar con precisión el límite entre lo que esta capability regula (ventana editable: `DRAFT`, `CONTENT_CHANGES_REQUESTED`) y lo que ya regulan `content-governance` (submit y la máquina de revisión semántica) y `visual-compliance` (estados visuales), sin duplicar ni contradecir sus requirements ya aceptados.

**Non-Goals:**
- No cambia código, endpoints ni comportamiento.
- No especifica `POST /creative-items/{id}/submit`: el endpoint vive físicamente en `creative/router.py`, pero su contrato completo (transiciones válidas, congelamiento de la versión enviada, idempotencia) ya es un ADDED Requirement de `009-content-governance` ("Submit de versión exacta y congelada"). Repetirlo aquí crearía dos fuentes de verdad para el mismo comportamiento.
- No especifica los estados `PENDING_VISUAL_REVIEW`, `VISUAL_CHANGES_REQUESTED` ni `FINAL_APPROVED` (propiedad de `visual-compliance`).

## Decisions

**El límite de esta capability es la ventana editable, no el enum completo de `workflow_status`.**
`CreativeWorkflowStatus` tiene 7 valores, pero `creative-studio` solo actúa mientras el item está en `DRAFT` o `CONTENT_CHANGES_REQUESTED` (`policies.EDITABLE_STATUSES`). Los otros 5 valores y sus transiciones son responsabilidad exclusiva de `content-governance`/`visual-compliance`. Alternativa descartada: declarar el enum completo aquí como "MODIFIED" de nada (no hay nada que modificar) o como referencia informativa — se prefirió no mencionarlo en absoluto en `## ADDED Requirements` para no crear una segunda descripción del mismo enum que pueda divergir con el tiempo; el enum vive únicamente en `009-content-governance` y `008-visual-compliance`.

**`/submit` no tiene un Requirement propio en esta capability.**
Aunque el código del endpoint vive en `creative/router.py`, su contrato de comportamiento (transiciones, congelamiento, idempotencia) ya está íntegramente spec'd por `009-content-governance`. Esta change lo menciona solo aquí, en design.md, como nota de ubicación de código — nunca en `## ADDED Requirements`, donde crearía una specificación paralela y potencialmente contradictoria.

**Verificación en vez of implementación.**
Como no hay código nuevo, `tasks.md` no tiene tareas de construcción: cada tarea apunta a un test ya existente (o a una inspección directa del código) que demuestra que el requirement redactado es verdad hoy. Si una verificación revela que el comportamiento real no coincide con lo redactado, el requirement se corrige para reflejar la realidad — el código y sus tests existentes son la autoridad, no esta spec.

## Risks / Trade-offs

- [Que un requirement quede redactado de forma más estricta o más laxa que el comportamiento real] → Cada requirement se verifica contra un test existente citado por nombre en `tasks.md`; ninguno se acepta sin esa referencia.
- [Que `content-governance`/`visual-compliance` ya hayan declarado algo que esta capability repita] → Se releyeron ambos `specs/*/spec.md` completos antes de redactar (ver headers de Requirement citados en `proposal.md`); el único punto de contacto (`/submit`, el enum `workflow_status`) se dejó explícitamente fuera de `## ADDED Requirements`.

## Migration Plan

No aplica: no hay despliegue ni rollback, es documentación de especificación sobre comportamiento ya en producción.

## Open Questions

(ninguna)
