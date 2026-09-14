import { useSession } from './useSession'

/**
 * Marca activa de la sesión. El `brand_id` y el rol provienen siempre de
 * `/api/v1/me`; el frontend nunca los deduce solo. Una identidad puede
 * pertenecer a varias marcas -- cuál es la "activa" es una elección de cliente
 * (`switchBrand`, persistida en localStorage), nunca autoridad de permisos:
 * cada endpoint sigue verificando membresía server-side para el `brand_id`
 * que efectivamente se envía.
 */
export function useActiveBrand(): {
  brandId: string
  brandName: string
  role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER'
} | null {
  const { profile } = useSession()
  const membership = profile?.activeMembership
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
