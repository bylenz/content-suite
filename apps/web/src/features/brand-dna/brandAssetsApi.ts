import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type { BrandAssetList, BrandAssetOut, BrandAssetType } from '../../shared/api/types'

/**
 * Server state de Brand Assets (change 012). Sigue el mismo patrón que Brand
 * Audit: el upload usa `FormData` (el navegador fija el boundary multipart;
 * `apiFetch` no fuerza `Content-Type` cuando el body no es JSON), y una
 * mutación exitosa invalida el listado propio. 403 (no-miembro en
 * subida/listado) y 404 (eliminar un asset inexistente/ajeno/sin membresía)
 * se propagan como `ApiError` para que la vista los presente por código.
 */

export function useBrandAssets(brandId: string) {
  return useQuery({
    queryKey: ['brand-assets', brandId],
    enabled: brandId !== '',
    queryFn: () => apiFetch<BrandAssetList>(`/api/v1/brands/${brandId}/assets`),
  })
}

function useInvalidateBrandAssets(brandId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['brand-assets', brandId] })
  }
}

/** Sube (o reemplaza, para PRIMARY_LOGO/ALT_LOGO) un brand asset. */
export function useUploadBrandAsset(brandId: string) {
  const invalidate = useInvalidateBrandAssets(brandId)
  return useMutation({
    mutationFn: ({ type, file }: { type: BrandAssetType; file: File }) => {
      const body = new FormData()
      body.append('type', type)
      body.append('file', file)
      return apiFetch<BrandAssetOut>(`/api/v1/brands/${brandId}/assets`, {
        method: 'POST',
        body,
      })
    },
    onSuccess: invalidate,
  })
}

/** Elimina un asset existente (logo o referencia visual individual). */
export function useDeleteBrandAsset(brandId: string) {
  const invalidate = useInvalidateBrandAssets(brandId)
  return useMutation({
    mutationFn: (assetId: string) =>
      apiFetch<undefined>(`/api/v1/brands/${brandId}/assets/${assetId}`, {
        method: 'DELETE',
      }),
    onSuccess: invalidate,
  })
}
