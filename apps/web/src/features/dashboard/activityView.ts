import type { ActivityEventOut } from '../../shared/api/types'

/**
 * Etiquetas honestas de los `event_type` que hoy tienen fuente persistida
 * (design.md: sin auditoría de IA ni Knowledge sync, que no tienen historial).
 * Un `event_type` futuro no listado aquí cae al fallback legible, nunca a un
 * texto inventado.
 */
const EVENT_TYPE_LABELS: Record<string, string> = {
  SUBMITTED: 'Contenido enviado a revisión',
  CONTENT_APPROVED: 'Contenido aprobado',
  CONTENT_CHANGES_REQUESTED: 'Cambios de contenido solicitados',
  PUBLISHED: 'Brand DNA publicado',
}

export function activityLabel(event: ActivityEventOut): string {
  return (
    EVENT_TYPE_LABELS[event.event_type] ??
    event.event_type.toLowerCase().replaceAll('_', ' ')
  )
}
