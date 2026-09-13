import { useCallback, useEffect, useMemo, useState } from 'react'
import { DEMO_ROLES, isDemoRole, type DemoRole } from './roles'
import { SessionContext, type ShellSession } from './session-context'

const STORAGE_KEY = 'content-suite.dev.demo-role'

function readStoredRole(): DemoRole {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && isDemoRole(stored)) return stored
  } catch {
    // localStorage puede estar bloqueado; se usa el rol por defecto
  }
  return 'creator'
}

/**
 * Provee la sesión del shell (ver `session-context.ts`).
 * Sin Supabase Auth todavía, el visitante queda anónimo; el modo demo se
 * entra explícitamente desde la vista de sesión faltante.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<ShellSession>({
    status: 'initializing',
    demoRole: 'creator',
  })

  useEffect(() => {
    // Bootstrap mínimo de la sesión (luego será Supabase Auth).
    const timer = window.setTimeout(() => {
      setSession((current) => ({ ...current, status: 'anonymous' }))
    }, 150)
    return () => window.clearTimeout(timer)
  }, [])

  /** Entrada explícita al shell demo. Es presentación, no autenticación. */
  const enterDemoSession = useCallback((role?: DemoRole) => {
    const target = role ?? readStoredRole()
    setSession({ status: 'authenticated', demoRole: target })
    try {
      window.localStorage.setItem(STORAGE_KEY, target)
    } catch {
      // Sin persistencia disponible; el cambio vive solo en memoria
    }
  }, [])

  const switchDemoRole = useCallback((role: DemoRole) => {
    setSession((current) => ({ ...current, demoRole: role }))
    try {
      window.localStorage.setItem(STORAGE_KEY, role)
    } catch {
      // Sin persistencia disponible; el cambio vive solo en memoria
    }
  }, [])

  const value = useMemo(() => {
    const index = DEMO_ROLES.indexOf(session.demoRole)
    const next = DEMO_ROLES[(index + 1) % DEMO_ROLES.length]
    return { ...session, enterDemoSession, switchDemoRole, nextDemoRole: next }
  }, [session, enterDemoSession, switchDemoRole])

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
