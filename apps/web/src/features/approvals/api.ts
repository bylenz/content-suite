import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type { DecisionOut, QueueOut, ReviewDetailOut, ReviewHistoryOut } from './types'

/**
 * Server state de Content Review. Una decisión exitosa invalida tanto la
 * cola/detalle de governance como el ítem de Creative (su `workflow_status`
 * cambió): las dos features leen el mismo estado de servidor, nunca lo
 * duplican en el cliente. Envelopes 403/404/409/422 se propagan como
 * `ApiError` para que la vista los presente por código.
 */

export function useReviewQueue(enabled = true) {
  return useQuery({
    queryKey: ['content-reviews', 'queue'],
    enabled,
    queryFn: () => apiFetch<QueueOut>('/api/v1/content-reviews/queue'),
  })
}

export function useReviewDetail(itemId: string) {
  return useQuery({
    queryKey: ['content-reviews', 'item', itemId],
    enabled: itemId !== '',
    queryFn: () => apiFetch<ReviewDetailOut>(`/api/v1/content-reviews/${itemId}`),
  })
}

export function useReviewHistory(itemId: string) {
  return useQuery({
    queryKey: ['content-reviews', 'item', itemId, 'history'],
    enabled: itemId !== '',
    queryFn: () => apiFetch<ReviewHistoryOut>(`/api/v1/content-reviews/${itemId}/history`),
  })
}

function useInvalidateReview() {
  const queryClient = useQueryClient()
  return (itemId: string) => {
    void queryClient.invalidateQueries({ queryKey: ['content-reviews'] })
    void queryClient.invalidateQueries({ queryKey: ['creative', 'item', itemId] })
  }
}

export function useApprove(itemId: string) {
  const invalidate = useInvalidateReview()
  return useMutation({
    mutationFn: () =>
      apiFetch<DecisionOut>(`/api/v1/content-reviews/${itemId}/approve`, { method: 'POST' }),
    onSuccess: () => invalidate(itemId),
  })
}

export function useRequestChanges(itemId: string) {
  const invalidate = useInvalidateReview()
  return useMutation({
    mutationFn: (feedback: string) =>
      apiFetch<DecisionOut>(`/api/v1/content-reviews/${itemId}/request-changes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      }),
    onSuccess: () => invalidate(itemId),
  })
}
