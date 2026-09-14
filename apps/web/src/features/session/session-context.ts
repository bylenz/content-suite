import { createContext } from 'react'
import type { Membership } from '../../shared/api/types'
import type { DemoRole } from './roles'

/**
 * Boundary de sesión del shell.
 *
 * La sesión se autentica exclusivamente tras un `GET /api/v1/me` 200 con el
 * token adjunto (de Supabase Auth o de una identidad de dev); la identidad y
 * el rol mostrados provienen solo de esa respuesta. Un token inválido,
 * ausente o expirado deja la sesión anónima. El frontend nunca es autoridad
 * de autorización.
 */
export type SessionStatus = 'initializing' | 'anonymous' | 'authenticated'

/** Identidad resuelta por la API (`/api/v1/me`). */
export interface SessionProfile {
  displayName: string
  email: string | null
  /** Primera membresía del workspace demo; null si la identidad no pertenece a marca alguna */
  membership: Membership | null
}

export interface SessionContextValue {
  status: SessionStatus
  profile: SessionProfile | null
  /** Identidad de dev seleccionada (solo selecciona el token adjunto) */
  selectedRole: DemoRole | null
  /** Identidades de dev con token disponible; vacío fuera de desarrollo */
  availableDevRoles: DemoRole[]
  /** Autentica con la identidad de dev indicada; sin token válido queda anónimo */
  authenticate: (role: DemoRole) => void
  /** Cambia de identidad invalidando antes todas las queries de marca */
  switchRole: (role: DemoRole) => void
  /** Siguiente identidad de dev en el ciclo del conmutador; null sin sesión */
  nextDevRole: DemoRole | null
  /** Motivo del último intento fallido de autenticación, si existe */
  authError: string | null
  /**
   * Envía un magic link de Supabase Auth al correo indicado. Devuelve el
   * mensaje de error si falla, o `null` si Supabase aceptó la solicitud (no
   * revela si el correo tiene o no una cuenta existente).
   */
  signInWithMagicLink: (email: string) => Promise<string | null>
  /** Cierra la sesión activa (Supabase Auth o identidad de dev) y vuelve a anónimo */
  signOut: () => Promise<void>
  /**
   * Vuelve a pedir `GET /api/v1/me` con el token actual y actualiza `profile`
   * en sitio (p. ej. tras crear un workspace nuevo). No cambia `status`; un
   * fallo aquí no fuerza logout, solo deja el perfil como estaba.
   */
  refreshProfile: () => Promise<void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)
