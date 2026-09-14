import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type { ActivityListResponse, PipelineOut } from '../../shared/api/types'

/** Tamaño de página del widget compacto de Dashboard (contrato: 1-50, default 20). */
export const ACTIVITY_PAGE_SIZE = 5

/** Desglose de Content Pipeline por los 7 estados reales (`GET .../pipeline`). */
export function usePipeline(brandId: string) {
  return useQuery({
    queryKey: ['dashboard', 'pipeline', brandId],
    queryFn: () =>
      apiFetch<PipelineOut>(`/api/v1/creative-items/pipeline?brand_id=${brandId}`),
    // Sin marca resuelta no hay autorización posible: no se consulta.
    enabled: brandId !== '',
  })
}

/** Feed paginado de Recent Activity (`GET /api/v1/activity`). */
export function useActivity(brandId: string, page: number) {
  return useQuery({
    queryKey: ['dashboard', 'activity', brandId, page],
    queryFn: () =>
      apiFetch<ActivityListResponse>(
        `/api/v1/activity?brand_id=${brandId}&limit=${ACTIVITY_PAGE_SIZE}&offset=${page * ACTIVITY_PAGE_SIZE}`,
      ),
    enabled: brandId !== '',
  })
}
