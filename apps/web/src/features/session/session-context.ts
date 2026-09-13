import { createContext } from 'react'
import type { DemoRole } from './roles'

/**
 * Boundary de sesión del shell.
 *
 * El frontend nunca es autoridad de autorización: este boundary solo decide
 * si existe una sesión para renderizar el shell. Por defecto el visitante es
 * anónimo y no ve el shell; el modo demo se entra de forma explícita y es
 * exclusivamente presentación — no autentica ni autoriza nada. La
 * autenticación real (Supabase Auth) y la autorización (membresías y roles)
 * llegan con changes posteriores y se resuelven en el backend.
 */
export type SessionStatus = 'initializing' | 'anonymous' | 'authenticated'

export interface ShellSession {
  status: SessionStatus
  /** Rol demo de presentación; no autoriza nada en el backend */
  demoRole: DemoRole
}

export interface SessionContextValue extends ShellSession {
  /** Entrada explícita al shell demo desde la vista anónima; no es autenticación */
  enterDemoSession: (role?: DemoRole) => void
  switchDemoRole: (role: DemoRole) => void
  nextDemoRole: DemoRole
}

export const SessionContext = createContext<SessionContextValue | null>(null)
