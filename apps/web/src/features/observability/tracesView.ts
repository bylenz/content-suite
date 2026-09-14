import type { BadgeVariant } from '@/components/ui/badge'
import type { TraceEntityType, TraceRecord } from '../../shared/api/types'

/**
 * Presentación honesta de los metadatos allowlist del trace (spec 07):
 * nunca se inventan estados ni se muestran datos que la facade no entrega.
 */

export const OUTCOME_VIEW: Record<TraceRecord['outcome'], { label: string; badge: BadgeVariant }> = {
  ok: { label: 'Éxito', badge: 'success' },
  error: { label: 'Error', badge: 'danger' },
}

export const ENTITY_TYPE_LABELS: Record<TraceEntityType, string> = {
  brand_dna_version: 'Versión de Brand DNA',
  creative_version: 'Versión de creative',
  visual_audit: 'Auditoría visual',
}

export function formatLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`
}

/** UUID corto legible para referencias de entidad/trace en filas densas. */
export function shortId(id: string | null): string {
  return id ? id.slice(0, 8) : '—'
}
