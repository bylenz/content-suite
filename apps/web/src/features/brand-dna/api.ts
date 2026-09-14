import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type {
  BrandBriefIn,
  BrandDnaDocument,
  BrandDnaOverview,
  BrandDnaVersion,
  BrandDnaVersionSummary,
  KnowledgeStatusOut,
} from '../../shared/api/types'

/** DNA vigente de la marca: `{active, draft}` según la matriz RBAC de lectura. */
export function useBrandDna(brandId: string) {
  return useQuery({
    queryKey: ['brand-dna', brandId],
    queryFn: () =>
      apiFetch<BrandDnaOverview>(`/api/v1/brands/${brandId}/brand-dna`),
  })
}

/** Historial de versiones (sin documento por entrada); el backend filtra DRAFT por rol. */
export function useBrandDnaVersions(brandId: string) {
  return useQuery({
    queryKey: ['brand-dna', brandId, 'versions'],
    queryFn: () =>
      apiFetch<{ versions: BrandDnaVersionSummary[] }>(
        `/api/v1/brands/${brandId}/brand-dna/versions`,
      ),
  })
}

/** Detalle de una versión publicada (documento íntegro). */
export function useBrandDnaVersion(brandId: string, version: number) {
  return useQuery({
    queryKey: ['brand-dna', brandId, 'versions', version],
    queryFn: () =>
      apiFetch<BrandDnaVersion>(`/api/v1/brands/${brandId}/brand-dna/versions/${version}`),
  })
}

function useInvalidateBrandDna(brandId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['brand-dna', brandId] })
  }
}

/** Upsert del borrador único (reemplazo completo del documento). */
export function useSaveDraft(brandId: string) {
  const invalidate = useInvalidateBrandDna(brandId)
  return useMutation({
    mutationFn: (document: BrandDnaDocument) =>
      apiFetch<BrandDnaVersion>(`/api/v1/brands/${brandId}/brand-dna/draft`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document }),
      }),
    onSuccess: invalidate,
  })
}

/**
 * Publicación transaccional con `expected_draft_id`. Un 409
 * (`INVALID_WORKFLOW_TRANSITION`) significa borrador desactualizado o
 * publicación concurrente: la mutación lo propaga para que la vista lo maneje.
 */
export function usePublishDraft(brandId: string) {
  const invalidate = useInvalidateBrandDna(brandId)
  return useMutation({
    mutationFn: (expectedDraftId: string) =>
      apiFetch<BrandDnaVersion>(`/api/v1/brands/${brandId}/brand-dna/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expected_draft_id: expectedDraftId }),
      }),
    onSuccess: invalidate,
    onError: invalidate,
  })
}

/**
 * Generación asistida por IA del borrador a partir de un brief (change 013):
 * invoca la AI Platform y persiste el resultado exactamente por el mismo
 * camino de upsert que `PATCH /draft` (reemplaza un borrador existente en el
 * mismo registro o crea la versión 1). No exige Knowledge sincronizada. Un
 * 503 (proveedor no configurado o salida inválida) no persiste ningún cambio.
 */
export function useGenerateBrandDna(brandId: string) {
  const invalidate = useInvalidateBrandDna(brandId)
  return useMutation({
    mutationFn: (brief: BrandBriefIn) =>
      apiFetch<BrandDnaVersion>(`/api/v1/brands/${brandId}/brand-dna/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief }),
      }),
    onSuccess: invalidate,
  })
}

/**
 * Sincronización explícita de Knowledge sobre la versión ACTIVE (solo Creator
 * según el backend). Idempotente sin desajuste; 409/503 se propagan con el
 * mensaje del envelope para mostrarse inline.
 */
export function useSyncKnowledge(brandId: string) {
  const invalidate = useInvalidateBrandDna(brandId)
  return useMutation({
    mutationFn: () =>
      apiFetch<KnowledgeStatusOut>(`/api/v1/brands/${brandId}/brand-knowledge/sync`, {
        method: 'POST',
      }),
    onSuccess: invalidate,
    onError: invalidate,
  })
}
