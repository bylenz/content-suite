import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type {
  DecisionOut,
  QueueOut,
  VisualAssetList,
  VisualAssetOut,
  VisualAuditHistoryOut,
  VisualAuditOut,
} from './types'

/**
 * Server state de Brand Audit (Visual Compliance). Sigue el mismo patrón que
 * Approvals/Creative: la mutación exitosa invalida la cola/detalle propios y
 * el ítem de Creative Studio (su `workflow_status` cambió). El upload usa
 * `FormData`: `apiFetch` no fuerza `Content-Type`, así que el navegador fija
 * el boundary multipart correcto. 403/404/409/422/503 se propagan como
 * `ApiError` (envelope centralizado) para que la vista los presente por código.
 */

export function useVisualQueue(enabled = true) {
  return useQuery({
    queryKey: ['visual-reviews', 'queue'],
    enabled,
    queryFn: () => apiFetch<QueueOut>('/api/v1/visual-reviews/queue'),
  })
}

export function useVisualAssets(itemId: string) {
  return useQuery({
    queryKey: ['visual-audit', 'item', itemId, 'assets'],
    enabled: itemId !== '',
    queryFn: () => apiFetch<VisualAssetList>(`/api/v1/creative-items/${itemId}/visual-assets`),
  })
}

export function useVisualAuditHistory(itemId: string) {
  return useQuery({
    queryKey: ['visual-audit', 'item', itemId, 'history'],
    enabled: itemId !== '',
    queryFn: () =>
      apiFetch<VisualAuditHistoryOut>(`/api/v1/creative-items/${itemId}/visual-audit-history`),
  })
}

/** El asset puede no tener auditoría todavía: la API responde 404 (no error). */
export function useLatestVisualAudit(assetId: string | null) {
  return useQuery({
    queryKey: ['visual-audit', 'asset', assetId, 'audit'],
    enabled: assetId !== null,
    retry: false,
    queryFn: () => apiFetch<VisualAuditOut>(`/api/v1/visual-assets/${assetId}/audit`),
  })
}

function useInvalidateVisual() {
  const queryClient = useQueryClient()
  return (itemId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ['visual-reviews'] })
    void queryClient.invalidateQueries({ queryKey: ['visual-audit'] })
    if (itemId) {
      void queryClient.invalidateQueries({ queryKey: ['creative', 'item', itemId] })
    }
  }
}

export function useUploadVisual(itemId: string) {
  const invalidate = useInvalidateVisual()
  return useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return apiFetch<VisualAssetOut>(`/api/v1/creative-items/${itemId}/visual-assets`, {
        method: 'POST',
        body,
      })
    },
    onSuccess: () => invalidate(itemId),
  })
}

export function useRunVisualAudit(itemId: string) {
  const invalidate = useInvalidateVisual()
  return useMutation({
    mutationFn: (assetId: string) =>
      apiFetch<VisualAuditOut>(`/api/v1/visual-assets/${assetId}/audit`, { method: 'POST' }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useApproveVisual(itemId: string) {
  const invalidate = useInvalidateVisual()
  return useMutation({
    mutationFn: ({ auditId, exceptionAccepted }: { auditId: string; exceptionAccepted: boolean }) =>
      apiFetch<DecisionOut>(`/api/v1/visual-audits/${auditId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exception_accepted: exceptionAccepted }),
      }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useRequestVisualChanges(itemId: string) {
  const invalidate = useInvalidateVisual()
  return useMutation({
    mutationFn: ({ auditId, feedback }: { auditId: string; feedback: string }) =>
      apiFetch<DecisionOut>(`/api/v1/visual-audits/${auditId}/request-changes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      }),
    onSuccess: () => invalidate(itemId),
  })
}
