/**
 * Formatters de presentación compartidos entre features.
 */
export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' })
}
