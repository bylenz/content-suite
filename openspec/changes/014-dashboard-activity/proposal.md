## Why

`003-dashboard-brand-dna-motion-polish` dejó Content Pipeline y Recent Activity deshabilitados a propósito ("la API actual no provee contratos para sus datos") y prohibió explícitamente mostrar números o eventos inventados que se confundan con producto real. Desde entonces se construyeron Creative Studio (`011`) y Content Governance (`009`), que ya persisten exactamente los datos que estos dos widgets necesitan: `workflow_status` por item y `workflow_events` append-only. El bloqueo original ya no existe para la mayor parte de lo que el mockup muestra — solo permanece bloqueado lo que depende de una fuente de evento que aún no existe (auditoría de IA marcada como actividad, sincronización de Knowledge como evento).

## What Changes

- Añade `GET /creative-items/pipeline?brand_id`: conteo de creative items por cada uno de los 7 valores reales de `workflow_status` de la marca — no la simplificación de 4 categorías que el mockup dibujaba antes de que el enum real existiera.
- Añade `GET /activity?brand_id&limit&offset`: feed paginado de actividad reciente, fusionando `workflow_events` (submit, decisiones de contenido y visuales) con un evento derivado por cada versión de Brand DNA publicada (`published_at`/`created_by`), en orden cronológico descendente — mismo shape de paginación que ya usa el facade de observabilidad (`limit` 1-50 default 20, `offset`, `total`).
- Reemplaza el placeholder `FutureCard` de Content Pipeline y Recent Activity, en las tres variantes de Dashboard (Creator, Content Reviewer, Visual Compliance Reviewer), por los widgets reales alimentados por estos dos endpoints.
- **No** incluye findings de auditoría de IA marcados como actividad ni eventos de sincronización de Knowledge: ninguno tiene hoy una fuente de evento persistida (ver design.md) y esta change no introduce una tabla de eventos nueva para cubrirlos — permanecen fuera de alcance, igual de explícitamente diferidos como el resto ya lo estaba en `003`.
- **BREAKING**: ninguno (endpoints nuevos; los placeholders reemplazados no eran contrato de nadie).

## Capabilities

### New Capabilities
- `dashboard-activity`: desglose de Content Pipeline por los 7 estados reales de workflow y feed paginado de Recent Activity derivado de eventos ya persistidos (`workflow_events` + publicaciones de Brand DNA), ambos scoped por membresía de marca, consumidos por las tres variantes de rol del Dashboard.

### Modified Capabilities
(ninguna — `dashboard-brand-dna-experience` de `003` cubre la experiencia visual/motion y no cambia; esta change solo reemplaza el contenido de dos placeholders que esa capability dejó explícitamente deshabilitados)

## Impact

- Código: nuevo endpoint de conteo (probablemente en `app/creative/`, ya dueño de `workflow_status`), nuevo endpoint de actividad (posiblemente `app/observability/` por cercanía de patrón, o un módulo propio — ver design.md), frontend en `apps/web/src/features/dashboard/DashboardPage.tsx` (reemplaza los dos `FutureCard` por widgets reales) y en las variantes de reviewer/visual-reviewer.
- Sin cambios de esquema: ambos endpoints leen tablas ya existentes (`creative_items`, `workflow_events`, `brand_dna_versions`), sin migración.
