import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type {
  AppliedContextOut,
  CreativeItemType,
  CreativeOutput,
  ItemList,
  ItemOut,
  VersionList,
  VersionOut,
} from './types'

/**
 * Server state de Creative Studio. La mutación exitosa invalida la jerarquía
 * `['creative', …]` de la marca/ítem afectado: item, versiones y contexto
 * aplicado se recalculan desde la respuesta real de la API.
 *
 * Errores: los envelopes 403/404/409/503 (KNOWLEDGE_NOT_AVAILABLE,
 * AI_OUTPUT_INVALID, SERVICE_UNAVAILABLE, INVALID_WORKFLOW_TRANSITION) se
 * propagan como `ApiError` para que la vista los presente por código.
 */

export function useCreativeItems(brandId: string) {
  return useQuery({
    queryKey: ['creative', 'items', brandId],
    enabled: brandId !== '',
    queryFn: () =>
      apiFetch<ItemList>(`/api/v1/creative-items?brand_id=${encodeURIComponent(brandId)}`),
  })
}

export function useCreativeItem(itemId: string) {
  return useQuery({
    queryKey: ['creative', 'item', itemId],
    enabled: itemId !== '',
    queryFn: () => apiFetch<ItemOut>(`/api/v1/creative-items/${itemId}`),
  })
}

export function useCreativeVersions(itemId: string) {
  return useQuery({
    queryKey: ['creative', 'item', itemId, 'versions'],
    enabled: itemId !== '',
    queryFn: () => apiFetch<VersionList>(`/api/v1/creative-items/${itemId}/versions`),
  })
}

/** Detalle read-only de una versión (spec 04: listar/ver versiones). */
export function useVersionDetail(itemId: string, versionId: string | null) {
  return useQuery({
    queryKey: ['creative', 'item', itemId, 'version', versionId],
    enabled: versionId !== null,
    queryFn: () =>
      apiFetch<VersionOut>(`/api/v1/creative-items/${itemId}/versions/${versionId}`),
  })
}

export function useAppliedContext(itemId: string) {
  return useQuery({
    queryKey: ['creative', 'item', itemId, 'applied-context'],
    enabled: itemId !== '',
    queryFn: () => apiFetch<AppliedContextOut>(`/api/v1/creative-items/${itemId}/applied-context`),
  })
}

function useInvalidateCreative() {
  const queryClient = useQueryClient()
  return (itemId?: string) => {
    if (itemId) {
      void queryClient.invalidateQueries({ queryKey: ['creative', 'item', itemId] })
    } else {
      void queryClient.invalidateQueries({ queryKey: ['creative'] })
    }
  }
}

export function useCreateItem() {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: (payload: {
      brand_id: string
      type: CreativeItemType
      title: string
      brief: Record<string, unknown>
    }) =>
      apiFetch<ItemOut>('/api/v1/creative-items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidate(),
  })
}

export function useCreateVersion(itemId: string) {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: (payload: { output: CreativeOutput }) =>
      apiFetch<VersionOut>(`/api/v1/creative-items/${itemId}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useGenerate(itemId: string) {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: () =>
      apiFetch<VersionOut>(`/api/v1/creative-items/${itemId}/generate`, { method: 'POST' }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useRegenerate(itemId: string) {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: () =>
      apiFetch<VersionOut>(`/api/v1/creative-items/${itemId}/regenerate`, { method: 'POST' }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useConsistencyCheck(itemId: string) {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: () =>
      apiFetch<VersionOut>(`/api/v1/creative-items/${itemId}/consistency-check`, {
        method: 'POST',
      }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useSubmit(itemId: string) {
  const invalidate = useInvalidateCreative()
  return useMutation({
    mutationFn: (versionId: string) =>
      apiFetch<ItemOut>(`/api/v1/creative-items/${itemId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version_id: versionId }),
      }),
    onSuccess: () => invalidate(itemId),
  })
}
