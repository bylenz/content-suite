import { useSession } from './useSession'

/**
 * Marca activa de la sesión (workspace demo de una sola marca). El `brand_id`
 * y el rol provienen de `/api/v1/me`; el frontend nunca los deduce solo.
 */
export function useActiveBrand(): {
  brandId: string
  brandName: string
  role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER'
} | null {
  const { profile } = useSession()
  const membership = profile?.membership
  if (!membership) return null
  return {
    brandId: membership.brand_id,
    brandName: membership.brand_name,
    role: membership.role,
  }
}

export function useIsCreator(): boolean {
  return useActiveBrand()?.role === 'CREATOR'
}
