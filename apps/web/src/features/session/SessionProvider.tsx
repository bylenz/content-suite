import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { apiFetch, setApiAuthToken } from '../../shared/api/client'
import type { Me } from '../../shared/api/types'
import { DEMO_ROLES, isDemoRole, type DemoRole } from './roles'
import { availableDevRoles, devTokenFor } from './devTokens'
import { supabase as defaultSupabaseClient } from './supabaseClient'
import { SessionContext, type SessionProfile, type SessionStatus } from './session-context'

const STORAGE_KEY = 'content-suite.dev.demo-role'

function readStoredRole(): DemoRole | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && isDemoRole(stored)) return stored
  } catch {
    // localStorage puede estar bloqueado; se arranca sin identidad seleccionada
  }
  return null
}

function toProfile(me: Me): SessionProfile {
  return {
    displayName: me.display_name ?? me.email ?? 'Miembro del workspace',
    email: me.email,
    membership: me.memberships[0] ?? null,
  }
}

/**
 * Provee la sesión del shell (ver `session-context.ts`).
 *
 * Dos fuentes de identidad conviven sin pisarse:
 * - Supabase Auth (magic link): única fuente en producción. El listener de
 *   `onAuthStateChange` es la autoridad — su evento `INITIAL_SESSION` (una
 *   vez por suscripción, con o sin sesión) resuelve el arranque, así que no
 *   hace falta un `getSession()` aparte ni el `setTimeout` que usaba el
 *   bootstrap de dev-only: la resolución async del SDK ya evita el cascade
 *   síncrono que ese timer prevenía.
 * - Identidades de dev (`devTokens.ts`): solo si `INITIAL_SESSION` no trae
 *   sesión de Supabase, se intenta reautenticar el rol de dev guardado. El
 *   conmutador solo selecciona qué entrada del mapping ignorado de tokens se
 *   adjunta; la sesión se consolida únicamente tras un `GET /api/v1/me` 200.
 * En ambos casos se limpian las queries de marca antes de reautenticar. El
 * token nunca se registra. `supabaseClient` es inyectable (default: el
 * singleton real) para que los tests no dependan de red ni de env vars.
 */
export function SessionProvider({
  children,
  supabaseClient = defaultSupabaseClient,
}: {
  children: React.ReactNode
  supabaseClient?: SupabaseClient | null
}) {
  const [status, setStatus] = useState<SessionStatus>('initializing')
  const [profile, setProfile] = useState<SessionProfile | null>(null)
  const [selectedRole, setSelectedRole] = useState<DemoRole | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const authenticate = useCallback(
    async (role: DemoRole) => {
      const token = devTokenFor(role)
      if (!token) {
        // Sin mapping (p. ej. build de producción o tokens no generados) no hay
        // sesión: anónimo, nunca un rol demostrativo.
        setApiAuthToken(null)
        setStatus('anonymous')
        setAuthError(null)
        return
      }
      setApiAuthToken(token)
      try {
        const me = await apiFetch<Me>('/api/v1/me')
        setProfile(toProfile(me))
        setSelectedRole(role)
        setStatus('authenticated')
        setAuthError(null)
        try {
          window.localStorage.setItem(STORAGE_KEY, role)
        } catch {
          // Sin persistencia disponible; la selección vive solo en memoria
        }
      } catch (error) {
        setApiAuthToken(null)
        setProfile(null)
        setSelectedRole(null)
        setStatus('anonymous')
        setAuthError(
          error instanceof Error
            ? error.message
            : 'No se pudo autenticar la identidad seleccionada',
        )
      }
    },
    [],
  )

  const switchRole = useCallback(
    (role: DemoRole) => {
      // La marca y sus permisos dependen de la identidad: se limpia el cache
      // de queries de marca antes de reautenticar para no filtrar datos entre
      // identidades.
      queryClient.removeQueries({ queryKey: ['brand-dna'] })
      void authenticate(role)
    },
    [authenticate, queryClient],
  )

  const hydrateFromSupabaseSession = useCallback(
    async (session: Session) => {
      queryClient.removeQueries({ queryKey: ['brand-dna'] })
      setApiAuthToken(session.access_token)
      try {
        const me = await apiFetch<Me>('/api/v1/me')
        setProfile(toProfile(me))
        setSelectedRole(null)
        setStatus('authenticated')
        setAuthError(null)
      } catch (error) {
        setApiAuthToken(null)
        setProfile(null)
        setStatus('anonymous')
        setAuthError(
          error instanceof Error ? error.message : 'No se pudo autenticar la sesión',
        )
      }
    },
    [queryClient],
  )

  useEffect(() => {
    if (!supabaseClient) {
      // Sin Supabase configurado (dev/test sin env vars): el único camino de
      // entrada es la identidad de dev previamente guardada, si existe.
      // Diferido un tick (mismo motivo que el bootstrap de dev original):
      // evita el cascade de un setState síncrono en el cuerpo del efecto.
      const timer = window.setTimeout(() => {
        const stored = readStoredRole()
        const initial = stored && devTokenFor(stored) ? stored : null
        if (initial) {
          void authenticate(initial)
        } else {
          setStatus('anonymous')
        }
      }, 0)
      return () => window.clearTimeout(timer)
    }
    const {
      data: { subscription },
    } = supabaseClient.auth.onAuthStateChange((event, session) => {
      if (session) {
        void hydrateFromSupabaseSession(session)
        return
      }
      if (event === 'INITIAL_SESSION') {
        // Sin sesión de Supabase: cae al rol de dev previamente guardado, si
        // existe. Un evento null posterior (p. ej. nuestro propio signOut)
        // ya deja el estado en anónimo de forma síncrona en signOut().
        const stored = readStoredRole()
        const initial = stored && devTokenFor(stored) ? stored : null
        if (initial) {
          void authenticate(initial)
        } else {
          setStatus('anonymous')
        }
      }
    })
    return () => subscription.unsubscribe()
  }, [supabaseClient, authenticate, hydrateFromSupabaseSession])

  const signInWithMagicLink = useCallback(
    async (email: string): Promise<string | null> => {
      if (!supabaseClient) {
        return 'El login no está configurado en este entorno.'
      }
      const { error } = await supabaseClient.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: window.location.origin },
      })
      return error ? error.message : null
    },
    [supabaseClient],
  )

  const signOut = useCallback(async () => {
    queryClient.removeQueries({ queryKey: ['brand-dna'] })
    try {
      window.localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Sin persistencia disponible; no hay nada que limpiar
    }
    setApiAuthToken(null)
    setProfile(null)
    setSelectedRole(null)
    setAuthError(null)
    setStatus('anonymous')
    if (supabaseClient) {
      await supabaseClient.auth.signOut()
    }
  }, [supabaseClient, queryClient])

  const value = useMemo(() => {
    const index = selectedRole ? DEMO_ROLES.indexOf(selectedRole) : -1
    const next = index >= 0 ? DEMO_ROLES[(index + 1) % DEMO_ROLES.length] : availableDevRoles()[0]
    return {
      status,
      profile,
      selectedRole,
      availableDevRoles: availableDevRoles(),
      authenticate: (role: DemoRole) => void authenticate(role),
      switchRole,
      authError,
      nextDevRole: next,
      signInWithMagicLink,
      signOut,
    }
  }, [
    status,
    profile,
    selectedRole,
    authenticate,
    switchRole,
    authError,
    signInWithMagicLink,
    signOut,
  ])

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
