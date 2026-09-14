import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type { TraceListResponse, TraceRecord } from '../../shared/api/types'

/** Límite de página del contrato (design.md 009: limit 1–50, default 20). */
export const TRACES_PAGE_SIZE = 20

export interface TraceFilters {
  /** Marca propia resuelta por sesión; el backend revalida la membresía. */
  brandId: string
  entityType?: string
  entityId?: string
  /** ISO 8601; los inputs de fecha del UI producen inicio/fin de día. */
  from?: string
  to?: string
}

/** Filtros allowlist del contrato; cualquier otro parámetro no se envía. */
function buildQuery(filters: TraceFilters, page: number): string {
  const params = new URLSearchParams()
  params.set('brand_id', filters.brandId)
  if (filters.entityType) params.set('entity_type', filters.entityType)
  // entity_id solo tiene sentido acompañando a entity_type (contrato).
  if (filters.entityId && filters.entityType) params.set('entity_id', filters.entityId)
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  params.set('limit', String(TRACES_PAGE_SIZE))
  params.set('offset', String(page * TRACES_PAGE_SIZE))
  return params.toString()
}

/** Listado paginado de traces de la marca activa con filtros allowlist. */
export function useTraces(filters: TraceFilters, page: number) {
  return useQuery({
    queryKey: ['traces', filters, page],
    queryFn: () => apiFetch<TraceListResponse>(`/api/v1/traces?${buildQuery(filters, page)}`),
    // Sin marca resuelta no hay autorización posible: no se consulta.
    enabled: filters.brandId !== '',
  })
}

/** Detalle sanitizado de un trace (`GET /api/v1/traces/{trace_id}`). */
export function useTrace(traceId: string | null) {
  return useQuery({
    queryKey: ['traces', 'detail', traceId],
    queryFn: () => apiFetch<TraceRecord>(`/api/v1/traces/${traceId}`),
    enabled: traceId !== null,
  })
}

/** Convierte `yyyy-mm-dd` de `input[type=date]` a ISO inicio/fin de día UTC. */
export function toDateIso(day: string, endOfDay: boolean): string | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return undefined
  return `${day}T${endOfDay ? '23:59:59.999' : '00:00:00.000'}Z`
}
