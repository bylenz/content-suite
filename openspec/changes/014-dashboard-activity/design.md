## Context

`003-dashboard-brand-dna-motion-polish` dejó ambos widgets como `FutureCard` (placeholder deshabilitado, sin prop de datos) precisamente porque "la API actual no provee contratos para sus datos", y prohibió explícitamente números/eventos estáticos que se confundan con producto real. Desde entonces, `creative_items.workflow_status` (7 valores) y `workflow_events` (append-only: `creative_item_id`, `event_type`, `actor_id`, `metadata`, `created_at`) ya existen y están poblados por Creative Studio (`011`) y Content Governance (`009`). `brand_dna_versions.published_at` (nullable, por fila) ya existe desde `002`. Ver `proposal.md - Why`.

## Goals / Non-Goals

**Goals:**
- Dar a los dos widgets ya dibujados en el mockup un contrato de datos real, apoyado exclusivamente en tablas que ya existen.
- Mantener la prohibición de `003` de no mostrar nunca un dato inventado: donde no hay fuente persistida, el widget simplemente no incluye esa categoría de evento — no se rellena con nada.

**Non-Goals:**
- No introduce una tabla de eventos nueva para cubrir auditoría de IA "flagged" o sincronización de Knowledge como actividad — ambas quedan fuera de alcance hasta que una change futura decida cómo persistirlas como evento (hoy solo existen como estado actual en columnas, no como historial).
- No replica el modo "agregado multi-marca sin `brand_id`" que el facade de observabilidad ofrece: Dashboard es una vista de un solo workspace activo (`useActiveBrand`), así que `brand_id` es siempre explícito, nunca opcional-para-agregar.
- No cambia `dashboard-brand-dna-experience` (003): la experiencia visual/motion que esa capability ya fija no se toca, solo se reemplaza el contenido de dos tarjetas que ella misma dejó como placeholder.

## Decisions

**Pipeline expone los 7 estados reales, no las 4 categorías del mockup.**
El mockup (`Draft/Pending/Approved/Rejected`) es anterior al enum real de 7 valores que `009`/`008` ya construyeron. Forzar esos 7 valores en 4 categorías requeriría una regla de mapeo inventada (¿`CONTENT_CHANGES_REQUESTED` y `VISUAL_CHANGES_REQUESTED` son ambos "Rejected"? ¿`PENDING_VISUAL_REVIEW` es "Pending" o algo distinto de `PENDING_CONTENT_REVIEW`?) que ningún documento de contrato responde. Se prefiere exponer el desglose honesto de 7 y dejar que el frontend decida cómo agrupar visualmente — evita que el backend tome una decisión de producto no pedida.

**Activity se limita a lo que tiene fuente persistida hoy: `workflow_events` + publicaciones de Brand DNA.**
El mockup muestra entradas de auditoría de IA ("AI Audit flagged tone mismatch") y de sincronización de Knowledge ("Content Suite synced AI Knowledge") que hoy no tienen ningún registro histórico — `consistency_result`/`consistency_score` viven en la versión creativa (estado actual, no evento), y `knowledge_status`/`knowledge_fingerprint` son columnas de estado actual en `brand_dna_versions`, sin timestamp de "cuándo terminó de sincronizar" separado. Añadir esas dos fuentes exigiría diseñar un event log nuevo — una decisión de mayor alcance que el propio `003` ya evitó tomar sin que se pidiera explícitamente. Se documenta como fuera de alcance en vez de aproximarlo con datos parciales o inventados, siguiendo la misma disciplina que `003` ya estableció.

**El feed es una consulta derivada (fusión en el momento de leer), no una tabla nueva.**
`workflow_events` y `brand_dna_versions.published_at` ya existen; el feed los combina y ordena en el endpoint de lectura, igual que el facade de observabilidad ya deriva su read-model sin introducir un event log paralelo para las trazas. Alternativa descartada: materializar un feed unificado en una tabla propia — añadiría un mecanismo de sincronización nuevo sin necesidad, cuando una consulta de fusión en el momento de leer ya es suficiente al volumen esperado (actividad de una marca, paginada).

**`brand_id` es siempre explícito y obligatorio, a diferencia del facade de observabilidad.**
Observability permite omitir `brand_id` para agregar todas las marcas del actor (una vista más administrativa). Dashboard, en cambio, siempre opera dentro del workspace activo de la sesión (`useActiveBrand.ts` ya fija ese concepto en el frontend) — no existe una vista "todas mis marcas" en el Dashboard hoy, así que no se replica esa opción aquí; mantiene la superficie del endpoint más simple que lo estrictamente necesario.

## Risks / Trade-offs

- [El desglose de 7 estados no coincide visualmente con el mockup original] → Es una decisión deliberada (ver arriba): el mockup quedó desactualizado por el propio enum que `009`/`008` introdujeron después; seguir el mockup al pie de la letra exigiría inventar una regla de agrupación no pedida por ningún documento.
- [Cobertura parcial de "actividad": sin auditoría de IA ni Knowledge sync] → Documentado como Non-Goal explícito, no como una omisión silenciosa; una change futura puede ampliar el feed si se decide invertir en un event log para esas dos fuentes.

## Migration Plan

No aplica migración de esquema (ambos endpoints leen tablas existentes sin cambios). Despliegue: agregar los dos endpoints de solo lectura y, en el mismo cambio de frontend, reemplazar los `FutureCard` — no hay estado intermedio inconsistente porque ninguno de los dos endpoints tiene efectos secundarios.

## Open Questions

(ninguna)
