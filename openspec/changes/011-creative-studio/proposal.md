## Why

`apps/api/app/creative/` y `apps/web/src/features/creative/` implementan Creative Studio por completo (creación de items, edición manual, generación asistida por IA, consistency-check, versionado inmutable) y `API.md`/`MODULES.md` lo documentan como un módulo entregado. Sin embargo, ninguna change de OpenSpec lo declara: `009-content-governance/proposal.md` referencia explícitamente "la change `008-creative-studio`" como la fuente de este contrato, pero ese número terminó reutilizado por `008-visual-compliance` y Creative Studio nunca se formalizó por separado. El resultado es un módulo completo en producción sin un contrato de especificación que lo respalde — `009-content-governance` y `008-visual-compliance` extienden su máquina de estados sin que exista una base documentada. Esta change cierra esa brecha documentando retroactivamente el comportamiento ya construido y verificado por sus tests existentes.

## What Changes

- Documenta como capability formal el módulo ya implementado: creación de creative items, lectura (items/versiones/contexto aplicado), edición manual como nueva versión, generación y regeneración asistidas por IA, consistency-check, y las reglas de autorización/validación que ya rigen estos endpoints.
- No se modifica ningún código: esta change es puramente de documentación de especificación sobre comportamiento existente y ya cubierto por tests (`apps/api/tests/test_creative_*.py`).
- **No incluye** la máquina de estados de revisión semántica (`DRAFT → PENDING_CONTENT_REVIEW → ...`) ni el endpoint `submit`: esos ya están íntegramente especificados por `009-content-governance` ("Submit de versión exacta y congelada", "Máquina de estados de revisión semántica protegida en backend"). Tampoco incluye los estados visuales (`PENDING_VISUAL_REVIEW`, etc.), especificados por `008-visual-compliance`. Esta change solo cubre lo que ocurre mientras un item está en una ventana editable (`DRAFT`, `CONTENT_CHANGES_REQUESTED`), antes de que exista una versión enviada a revisión.
- **BREAKING**: ninguno.

## Capabilities

### New Capabilities
- `creative-studio`: creación y lectura de creative items y sus versiones, edición manual y generación/regeneración asistida por IA restringidas a la ventana editable, consistency-check contra Brand Knowledge con score calculado en backend, contexto aplicado siempre relativo a la última versión, y las reglas de autorización (CREATOR escribe, cualquier miembro lee, 404 sin membresía) y validación (tipos estrictos, brief ≤16KB, applied_rule_ids verificados contra el contexto recuperado) que ya gobiernan estos endpoints.

### Modified Capabilities
(ninguna — `content-governance` y `visual-compliance` ya son dueños de la máquina de estados de revisión y no se tocan aquí)

## Impact

- Código: ninguno (documentación retroactiva). Endpoints ya existentes bajo `/api/v1/creative-items` (`apps/api/app/creative/router.py`).
- Specs: nueva capability `creative-studio`; sin deltas sobre `content-governance` ni `visual-compliance`.
- Riesgo de desalineación: si algún requisito redactado aquí no coincide con el comportamiento real verificado en tasks.md, el comportamiento real (código + tests) es la autoridad — se corrige el requisito, no el código, salvo que el propio proceso de verificación descubra un bug real.
