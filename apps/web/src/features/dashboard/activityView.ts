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

/** Tono del punto de actividad: derivado del `event_type` real, con
 * fallback neutro para tipos no listados. */
export type ActivityTone = 'success' | 'danger' | 'info' | 'deep' | 'neutral'

export function activityTone(event: ActivityEventOut): ActivityTone {
  const type = event.event_type
  if (type.endsWith('APPROVED')) return 'success'
  if (type.endsWith('CHANGES_REQUESTED')) return 'danger'
  if (type === 'SUBMITTED' || type.endsWith('UPLOADED')) return 'info'
  if (type === 'PUBLISHED') return 'deep'
  return 'neutral'
}
