import { createContext } from 'react'
import type { Membership } from '../../shared/api/types'

/**
 * Boundary de sesión del shell.
 *
 * La sesión se autentica exclusivamente tras un `GET /api/v1/me` 200 con el
 * access token de Supabase Auth adjunto; la identidad, las membresías y el
 * rol mostrados provienen solo de esa respuesta (base de datos real). Un
 * token inválido, ausente o expirado deja la sesión anónima. El frontend
 * nunca es autoridad de autorización.
 */
export type SessionStatus = 'initializing' | 'anonymous' | 'authenticated'

/** Identidad resuelta por la API (`/api/v1/me`). */
export interface SessionProfile {
  displayName: string
  email: string | null
  /** Todas las marcas a las que pertenece esta identidad (posiblemente varias) */
  memberships: Membership[]
  /**
   * Marca activa elegida por el usuario (`switchBrand`) o, por defecto, la
   * primera membresía; null si la identidad no pertenece a marca alguna.
   */
  activeMembership: Membership | null
}

export interface SessionContextValue {
  status: SessionStatus
  profile: SessionProfile | null
  /** Motivo del último intento fallido de autenticación, si existe */
  authError: string | null
  /**
   * Inicia sesión con correo + contraseña contra Supabase Auth. Devuelve el
   * mensaje de error si falla (credenciales inválidas, etc.), o `null` si la
   * sesión se estableció -- el listener de `onAuthStateChange` la recoge.
   */
  signInWithPassword: (email: string, password: string) => Promise<string | null>
  /** Cierra la sesión activa de Supabase Auth y vuelve a anónimo */
  signOut: () => Promise<void>
  /**
   * Vuelve a pedir `GET /api/v1/me` con el token actual y actualiza `profile`
   * en sitio (p. ej. tras crear un workspace nuevo). Si se indica
   * `activateBrandId`, esa membresía queda como activa (persistida) y se
   * limpian las queries de marca. No cambia `status`; un fallo aquí no
   * fuerza logout, solo deja el perfil como estaba.
   */
  refreshProfile: (activateBrandId?: string) => Promise<void>
  /**
   * Cambia la marca activa entre las membresías ya presentes en `profile`
   * (nunca pide una nueva autenticación: es la misma identidad, otra marca).
   * Persiste la elección en localStorage y limpia las queries de marca para
   * que ningún widget muestre datos de la marca anterior. No-op si `brandId`
   * no está entre las membresías de la identidad actual.
   */
  switchBrand: (brandId: string) => void
}

export const SessionContext = createContext<SessionContextValue | null>(null)
