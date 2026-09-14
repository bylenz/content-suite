/**
 * Mapping ignorado rol -> token de dev (`apps/web/.env.development.local`).
 * Solo existe en builds de desarrollo: `import.meta.env.DEV` es estático y en
 * producción la lectura del mapping queda fuera del código ejecutable.
 * El token nunca se registra ni se commitea; expira a los 15 minutos.
 */
import { DEMO_ROLES, type DemoRole } from './roles'

const TOKEN_BY_ROLE: Record<DemoRole, string | undefined> = {
  creator: import.meta.env.VITE_DEV_API_TOKEN_CREATOR,
  content_reviewer: import.meta.env.VITE_DEV_API_TOKEN_CONTENT_REVIEWER,
  visual_reviewer: import.meta.env.VITE_DEV_API_TOKEN_VISUAL_REVIEWER,
}

/** Token de dev para la identidad seleccionada; undefined fuera de DEV o sin mapping. */
export function devTokenFor(role: DemoRole): string | undefined {
  if (!import.meta.env.DEV) return undefined
  const token = TOKEN_BY_ROLE[role]
  return token && token.length > 0 ? token : undefined
}

/** Identidades de dev con token disponible en el mapping (vacío en producción). */
export function availableDevRoles(): DemoRole[] {
  if (!import.meta.env.DEV) return []
  return DEMO_ROLES.filter((role) => devTokenFor(role) !== undefined)
}
