import type { BadgeVariant } from '@/components/ui/badge'
import type { BrandDnaStatus, KnowledgeStatus } from '../../shared/api/types'

// `formatDate` se movió a `shared/format.ts` (change 009): formatter
// compartido entre features; se reexporta para no tocar las vistas brand-dna.
export { formatDate } from '../../shared/format'

/**
 * Presentación honesta del estado de Knowledge según WORKFLOWS: cinco estados
 * reales. La sincronización es siempre explícita (nunca automática): el Creator
 * la dispara desde Brand DNA. `OUTDATED` significa que hay un borrador con
 * cambios pendientes de publicar; el Knowledge publicado sigue sirviendo la
 * versión activa y el sync queda deshabilitado hasta publicar.
 * `badge` es la variante del primitive Badge; `banner` conserva clases para
 * los avisos amplios no-Badge.
 */
export const KNOWLEDGE_STATUS_VIEW: Record<
  KnowledgeStatus,
  { label: string; badge: BadgeVariant; banner: string }
> = {
  NOT_SYNCED: {
    label: 'Pendiente de sincronización',
    badge: 'info',
    banner: 'bg-info-bg text-info-fg',
  },
  SYNCING: {
    label: 'Sincronizando',
    badge: 'info',
    banner: 'bg-info-bg text-info-fg',
  },
  SYNCED: {
    label: 'Sincronizado',
    badge: 'success',
    banner: 'bg-success-bg text-success-fg',
  },
  OUTDATED: {
    label: 'Borrador pendiente de publicar',
    badge: 'warning',
    banner: 'bg-warning-bg text-warning-fg',
  },
  FAILED: {
    label: 'Sincronización fallida',
    badge: 'danger',
    banner: 'bg-danger-bg text-danger-fg',
  },
}

export const VERSION_STATUS_VIEW: Record<BrandDnaStatus, { label: string; badge: BadgeVariant }> = {
  DRAFT: { label: 'Borrador', badge: 'info' },
  ACTIVE: { label: 'Activa', badge: 'success' },
  ARCHIVED: { label: 'Archivada', badge: 'neutral' },
}
