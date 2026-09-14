## Why

`002-brand-dna-authoring/design.md` deja fuera de alcance, explícitamente, la generación asistida por IA del borrador de Brand DNA. El mockup (`starter-design/Content Suite.dc.html`) muestra el flujo de onboarding completo ("Brand Brief → AI Brand DNA → Human Review → AI Knowledge") con una pantalla de brief y un botón "Generate Brand DNA", `API.md` ya lista la ruta `POST /api/v1/brands/{brand_id}/brand-dna/generate`, y `app/ai/prompts.py` ya registra el prompt `brand.architect.v1` para esto — pero nadie lo invoca. Sin esta capability, todo brand nuevo empieza su Brand DNA desde una autoría manual completa de las cinco secciones, contradiciendo el flujo de onboarding que el propio producto ya diseñó.

## What Changes

- Añade `POST /brands/{brand_id}/brand-dna/generate`: a partir de un brief estructurado (datos básicos de marca, audiencia, personalidad/tono, reglas siempre/nunca), genera el `BrandDnaDocument` completo (las cinco secciones) vía la AI Platform y lo persiste como el DRAFT de la marca, usando exactamente el mismo camino de upsert (`_apply_draft_upsert`) que la autoría manual ya usa — mismo lock, mismo efecto de marcar la versión ACTIVE `OUTDATED` en Knowledge.
- Añade un nuevo contrato estructurado en `app/ai/contracts.py` para la salida de generación (ver `design.md` por qué no se reutiliza `BrandDnaDocument` de `app/brand_dna/schemas.py` tal cual), lo que exige ampliar el tipo genérico `ContractT` de `run_capability` (hoy cerrado a `CreativeOutput | ConsistencyResult | VisualAuditResult`) y el `Literal` de `TraceSummary.contract`.
- Añade una columna `brief` (jsonb, nullable) a `brand_dna_versions` para conservar el brief que originó una generación — hoy no existe ninguna columna para esto (a diferencia de `creative_versions`, que sí guarda su brief).
- **No** depende de Brand Knowledge/RAG: a diferencia de la generación de Creative Studio, esta generación ocurre *antes* de que exista ninguna Brand Knowledge sincronizada (Knowledge se deriva de Brand DNA, no al revés), así que no hay contexto de retrieval que recuperar ni exigencia de `SYNCED`.
- **BREAKING**: ninguno (endpoint y columna nuevos; el flujo de autoría manual existente no cambia).

## Capabilities

### New Capabilities
(ninguna — se extiende `brand-dna`, ya existente desde `002-brand-dna-authoring`)

### Modified Capabilities
- `brand-dna`: agrega la generación asistida por IA del borrador (`POST .../generate`) como una segunda forma de producir el documento que se persiste por el mismo camino de upsert que la autoría manual; ningún requirement existente de `002` cambia de comportamiento.

## Impact

- Código: `app/brand_dna/` (nuevo endpoint + wiring de generación), `app/ai/contracts.py` (nuevo contrato, ampliación de `run_capability`/`TraceSummary`), `app/ai/prompts.py` (activa `brand.architect.v1`, ya registrado), migración Alembic (columna `brief`).
- Frontend: pantalla de brief de onboarding (`apps/web/src/features/brand-dna/`), acorde a `starter-design/Content Suite.dc.html`.
- Sin cambios de contrato en `002-brand-dna-authoring`'s requirements existentes.
