/**
 * Roles demo del workspace. Solo presentación: la autoridad de roles y
 * membresías vive en el backend (FastAPI). Este archivo no participa en
 * decisiones de acceso de dominio.
 */
export const DEMO_ROLES = ['creator', 'content_reviewer', 'visual_reviewer'] as const

export type DemoRole = (typeof DEMO_ROLES)[number]

export interface RoleProfile {
  id: DemoRole
  label: string
  /** Nombre demo para el avatar del shell (dato de demostración, no dominio) */
  demoName: string
}

export const ROLE_PROFILES: Record<DemoRole, RoleProfile> = {
  creator: { id: 'creator', label: 'Creator', demoName: 'Elena' },
  content_reviewer: {
    id: 'content_reviewer',
    label: 'Content Reviewer',
    demoName: 'Maria',
  },
  visual_reviewer: {
    id: 'visual_reviewer',
    label: 'Visual Compliance Reviewer',
    demoName: 'Diego',
  },
}

export function isDemoRole(value: string): value is DemoRole {
  return (DEMO_ROLES as readonly string[]).includes(value)
}

/** Marca demo del workspace; los datos reales serán seeds del backend. */
export const DEMO_WORKSPACE = { name: 'Kinu' } as const
