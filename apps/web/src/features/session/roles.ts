import type { BrandRole } from '../../shared/api/types'

/**
 * Identidades demo de desarrollo. Solo seleccionan qué entrada del mapping
 * ignorado de tokens se adjunta; la identidad y el rol reales provienen
 * siempre de la respuesta de `GET /api/v1/me` (backend).
 */
export const DEMO_ROLES = ['creator', 'content_reviewer', 'visual_reviewer'] as const

export type DemoRole = (typeof DEMO_ROLES)[number]

export function isDemoRole(value: string): value is DemoRole {
  return (DEMO_ROLES as readonly string[]).includes(value)
}

/** Etiquetas legibles de los roles resueltos por el backend. */
export const ROLE_LABELS: Record<BrandRole, string> = {
  CREATOR: 'Creator',
  CONTENT_REVIEWER: 'Content Reviewer',
  VISUAL_REVIEWER: 'Visual Compliance Reviewer',
}

/** Fallback de presentación mientras la sesión no resuelve la marca real. */
export const WORKSPACE_FALLBACK_NAME = 'Workspace'
