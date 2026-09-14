## Context

`002-brand-dna-authoring` ya construyó la autoría manual completa: `PATCH /draft` (upsert bajo lock de marca, `_apply_draft_upsert` en `app/brand_dna/service.py`), publicación versionada e inmutable, y el estado de Knowledge sin sincronización. `app/ai/prompts.py` ya registra `brand.architect.v1` sin que nada lo invoque, y `API.md` ya lista la ruta de generación sin body documentado. Ver `proposal.md - Why`.

## Goals / Non-Goals

**Goals:**
- Generar el `BrandDnaDocument` completo desde un brief, reutilizando el camino de persistencia que la autoría manual ya construyó (sin un mecanismo de guardado paralelo).
- Decidir cómo el AI Platform (hoy cerrado a tres contratos) admite un cuarto sin romper el patrón de `run_capability`.

**Non-Goals:**
- No genera ni consume Brand Knowledge: esta capability es anterior a que exista cualquier Knowledge sincronizada.
- No cambia la publicación, el historial de versiones ni los contratos de lectura por rol que `002` ya especifica — ninguno de esos requirements se toca.
- No incluye edición asistida por IA de un documento ya existente (regenerar parcialmente una sección) — la generación siempre produce el documento completo desde cero a partir del brief.

## Decisions

**Nuevo contrato en `app/ai/contracts.py`, no reutilizar `BrandDnaDocument` de `app/brand_dna/schemas.py` directamente.**
`app/ai/contracts.py` es la frontera de contratos de la AI Platform (AI_SYSTEM.md); el patrón ya establecido por Creative es que el dominio importa *desde* `app.ai.contracts` (`creative/schemas.py` hace `from app.ai.contracts import CreativeOutput, RuleRef`), nunca al revés. `BrandDnaDocument` hoy vive en `app/brand_dna/schemas.py` porque nació antes de que existiera generación. Esta change mueve su definición estricta (las cinco secciones, límites de tamaño) a `app/ai/contracts.py` como el contrato validado por `run_capability`, y `app/brand_dna/schemas.py` pasa a importarlo desde ahí — mismo documento, una sola definición, dirección de dependencia consistente con Creative. Alternativa descartada: mantener dos tipos (uno en cada módulo) y convertir entre ellos — duplica los límites de validación (32KB, longitudes por campo) con riesgo real de que diverjan silenciosamente.

**Ampliar el `ContractT` de `run_capability` y el `Literal` de `TraceSummary.contract`.**
`app/ai/runner.py` declara `RunResult[ContractT: (CreativeOutput, ConsistencyResult, VisualAuditResult)]`; esta change agrega el contrato de Brand DNA a esa tupla de restricción y a `TraceSummary.contract`. Es un cambio mecánico (agregar un elemento a una tupla de tipos y a un `Literal`), no una reestructuración: `build_trace_summary` gana una rama más, siguiendo el mismo patrón `isinstance` que ya usa para los otros tres.

**Sin contexto de retrieval: la generación es una llamada directa brief → documento.**
A diferencia de `creative.generate`, que exige Brand Knowledge `SYNCED` y construye contexto híbrido antes de invocar el modelo, la generación de Brand DNA no tiene de dónde recuperar contexto: Knowledge todavía no existe en este punto del ciclo de vida de una marca nueva. El prompt `brand.architect.v1` ya está escrito para recibir el brief directamente sin contexto adicional. Alternativa descartada: exigir alguna Brand Knowledge previa como "ejemplo" — no hay ninguna fuente de la que derivarla antes de que exista un Brand DNA publicado.

**Nueva columna `brief` (jsonb, nullable) en `brand_dna_versions`.**
Mismo patrón que `creative_versions.brief` (también jsonb, también solo presente cuando hay un origen que lo produjo). Nullable porque una versión nacida de autoría manual pura, o una versión anterior a esta change, no tiene brief. Alternativa descartada: no persistir el brief en absoluto — se perdería la posibilidad de mostrarlo en la revisión humana del borrador generado (el mockup muestra la pantalla de brief como parte del mismo flujo de revisión) y de reutilizarlo si el Creator quiere regenerar ajustando solo un campo.

**Generar sobre un DRAFT existente lo reemplaza sin advertencia adicional.**
`_apply_draft_upsert` ya reemplaza el documento completo del DRAFT en su fila existente cuando uno ya existe (confirmado leyendo `app/brand_dna/service.py:105-133`); generar es solo otra forma de producir el `document` que se le pasa a esa misma función, así que hereda ese comportamiento sin cambios. No se introduce ninguna guarda nueva contra sobrescritura que la autoría manual (`PATCH /draft`) tampoco tiene hoy — sería una asimetría no justificada por ningún requirement existente.

## Risks / Trade-offs

- [Mover `BrandDnaDocument` a `app/ai/contracts.py` toca un archivo ya usado por `002`] → Es un movimiento de definición, no un cambio de forma: los campos, límites y validadores existentes de `002` se preservan exactamente; solo cambia el módulo que lo define y la dirección del import en `brand_dna/schemas.py`. Ningún requirement de `002` depende de en qué archivo vive el tipo.
- [Ampliar el `Literal` de `TraceSummary` y el `ContractT` de `run_capability` son cambios en un módulo compartido por Creative Studio y el resto de la AI Platform] → Ambos son adiciones puras (un elemento más en una tupla de tipos / un valor más en un Literal), no modifican el comportamiento de los tres contratos existentes; se verifican con la suite completa de `test_ai_*.py` y `test_creative_ai.py` sin cambios esperados en esos tests.

## Migration Plan

1. Migración Alembic: columna `brief` (jsonb, nullable) en `brand_dna_versions`.
2. Mover `BrandDnaDocument` (y sus sub-secciones) a `app/ai/contracts.py`; actualizar el import en `app/brand_dna/schemas.py`.
3. Ampliar `ContractT` en `app/ai/runner.py` y el `Literal` de `TraceSummary.contract`; agregar la rama correspondiente en `build_trace_summary`.
4. Implementar `generate` en `app/brand_dna/service.py` reutilizando `_apply_draft_upsert`; wiring del endpoint en el router con los mismos `Depends` de adapter/tracer que ya usa Creative.
5. Rollback: revertir el código; la columna `brief` puede quedar (nullable, no rompe nada) o revertirse en una migración `downgrade` si se prefiere.

## Open Questions

(ninguna)
