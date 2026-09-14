import type { BrandRole } from '../../shared/api/types'

/** Etiquetas legibles de los roles resueltos por el backend (`/api/v1/me`). */
export const ROLE_LABELS: Record<BrandRole, string> = {
  CREATOR: 'Creator',
  CONTENT_REVIEWER: 'Content Reviewer',
  VISUAL_REVIEWER: 'Visual Compliance Reviewer',
}

/** Fallback de presentación mientras la sesión no resuelve la marca real. */
export const WORKSPACE_FALLBACK_NAME = 'Workspace'
