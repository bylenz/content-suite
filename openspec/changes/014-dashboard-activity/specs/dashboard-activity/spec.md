## Purpose

Expone, para una marca donde el actor tiene membresía, el desglose real de creative items por estado de workflow y un feed paginado de actividad reciente derivado de eventos ya persistidos — los dos contratos de datos que `003-dashboard-brand-dna-motion-polish` dejó pendientes al mantener Content Pipeline y Recent Activity deshabilitados.

## ADDED Requirements

### Requirement: Desglose de Content Pipeline por estado real de workflow
El sistema SHALL exponer, para una marca donde el actor tiene membresía, un conteo de creative items agrupado por cada uno de los 7 valores reales de `workflow_status` (`DRAFT`, `PENDING_CONTENT_REVIEW`, `CONTENT_CHANGES_REQUESTED`, `CONTENT_APPROVED`, `PENDING_VISUAL_REVIEW`, `VISUAL_CHANGES_REQUESTED`, `FINAL_APPROVED`) — nunca una simplificación en menos categorías. El conteo SHALL incluir los estados sin ningún item con valor cero, nunca omitirlos. Solicitar el desglose de una marca sin membresía responde 403.

#### Scenario: Desglose refleja los estados reales
- **WHEN** se consulta el pipeline de una marca con items en varios estados
- **THEN** la respuesta incluye un conteo por cada uno de los 7 estados posibles, con cero en los que no tienen items

#### Scenario: Sin membresía
- **WHEN** un usuario sin membresía en la marca solicita su pipeline
- **THEN** la respuesta es 403

### Requirement: Feed de actividad reciente basado en eventos ya persistidos
El sistema SHALL exponer, para una marca donde el actor tiene membresía, un feed paginado de actividad reciente derivado de `workflow_events` (submit, decisiones de contenido y visuales, con su actor, tipo de evento y momento) en orden cronológico descendente, con paginación `limit` (1-50, default 20) y `offset`, devolviendo el total real disponible — mismo shape de paginación que ya usa el facade de observabilidad. El feed SHALL incluir, además, un evento derivado por cada versión de Brand DNA de la marca que fue publicada (`published_at` no nulo), fusionado cronológicamente con los eventos de workflow. Esta capability MUST NOT inventar categorías de evento sin una fuente persistida: findings de auditoría de IA marcados como actividad y sincronizaciones de Knowledge quedan fuera de este feed hasta que exista una fuente de evento persistida para ellos.

#### Scenario: Feed fusiona workflow y publicaciones de Brand DNA
- **WHEN** una marca tiene eventos de workflow y al menos una versión de Brand DNA publicada
- **THEN** el feed los muestra fusionados en un único orden cronológico descendente

#### Scenario: Paginación
- **WHEN** se solicita el feed con `limit`/`offset`
- **THEN** la respuesta devuelve como máximo `limit` entradas (1-50, default 20) a partir de `offset`, junto con el total real disponible

#### Scenario: Sin membresía
- **WHEN** un usuario sin membresía en la marca solicita su feed de actividad
- **THEN** la respuesta es 403

### Requirement: Los widgets dejan de mostrarse como "Próximamente"
Las superficies de Dashboard para los tres roles (Creator, Content Reviewer, Visual Compliance Reviewer) SHALL reemplazar el placeholder deshabilitado de Content Pipeline y Recent Activity por los datos reales de estos dos endpoints. Ninguna superficie SHALL mostrar un número o evento inventado en el cliente. Cada rol MAY resaltar un subconjunto distinto del mismo desglose completo (p. ej. el Content Reviewer resalta `PENDING_CONTENT_REVIEW`) pero consume los mismos dos endpoints, no una variante por rol.

#### Scenario: Sin datos reales aún disponibles
- **WHEN** una marca no tiene ningún creative item ni evento
- **THEN** el widget muestra su estado vacío real (conteos en cero, feed vacío), nunca el placeholder "Próximamente" ni un dato de ejemplo
