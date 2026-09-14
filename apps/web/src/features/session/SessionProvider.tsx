import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { apiFetch, setApiAuthToken } from '../../shared/api/client'
import type { Me, Membership } from '../../shared/api/types'
import { supabase as defaultSupabaseClient } from './supabaseClient'
import { SessionContext, type SessionProfile, type SessionStatus } from './session-context'

const ACTIVE_BRAND_STORAGE_KEY = 'content-suite.active-brand-id'

/** Query keys cuya raíz cuelga de una marca (ver cada `api.ts` de feature). */
const BRAND_SCOPED_QUERY_KEYS = [
  'brand-dna',
  'brand-assets',
  'creative',
  'content-reviews',
  'dashboard',
  'traces',
  'visual-audit',
  'visual-reviews',
] as const

function readStoredActiveBrandId(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_BRAND_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeActiveBrandId(brandId: string) {
  try {
    window.localStorage.setItem(ACTIVE_BRAND_STORAGE_KEY, brandId)
  } catch {
    // Sin persistencia disponible; la elección vive solo en memoria de esta sesión
  }
}

function clearBrandScopedQueries(queryClient: QueryClient) {
  for (const key of BRAND_SCOPED_QUERY_KEYS) {
    queryClient.removeQueries({ queryKey: [key] })
  }
}

function pickActiveMembership(memberships: Membership[]): Membership | null {
  const preferred = readStoredActiveBrandId()
  const match = preferred ? memberships.find((m) => m.brand_id === preferred) : undefined
  return match ?? memberships[0] ?? null
}

function toProfile(me: Me): SessionProfile {
  return {
    displayName: me.display_name ?? me.email ?? 'Miembro del workspace',
    email: me.email,
    memberships: me.memberships,
    activeMembership: pickActiveMembership(me.memberships),
  }
}

/**
 * Provee la sesión del shell (ver `session-context.ts`).
 *
 * Única fuente de identidad: Supabase Auth (correo + contraseña). El listener
 * de `onAuthStateChange` es la autoridad — su evento `INITIAL_SESSION` (una
 * vez por suscripción, con o sin sesión) resuelve el arranque. Con sesión se
 * adjunta el access token y la sesión del shell se consolida únicamente tras
 * un `GET /api/v1/me` 200: perfil, membresías y rol vienen siempre de la base
 * de datos, nunca de datos locales. Antes de reautenticar se limpian las
 * queries de marca. El token nunca se registra. `supabaseClient` es
 * inyectable (default: el singleton real) para que los tests no dependan de
 * red ni de env vars; sin cliente configurado la sesión queda anónima.
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
  const [authError, setAuthError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const hydrateFromSupabaseSession = useCallback(
    async (session: Session) => {
      clearBrandScopedQueries(queryClient)
      setApiAuthToken(session.access_token)
      try {
        const me = await apiFetch<Me>('/api/v1/me')
        setProfile(toProfile(me))
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
      // Sin Supabase configurado (dev/test sin env vars) no hay forma de
      // entrar: la sesión queda anónima y el login lo explica. Diferido un
      // tick para evitar un setState síncrono en el cuerpo del efecto.
      const timer = window.setTimeout(() => setStatus('anonymous'), 0)
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
        // Sin sesión de Supabase al arrancar: anónimo. Un evento null
        // posterior (p. ej. nuestro propio signOut) ya deja el estado en
        // anónimo de forma síncrona en signOut().
        setStatus('anonymous')
      }
    })
    return () => subscription.unsubscribe()
  }, [supabaseClient, hydrateFromSupabaseSession])

  const signInWithPassword = useCallback(
    async (email: string, password: string): Promise<string | null> => {
      if (!supabaseClient) {
        return 'El login no está configurado en este entorno.'
      }
      const { error } = await supabaseClient.auth.signInWithPassword({ email, password })
      return error ? error.message : null
    },
    [supabaseClient],
  )

  const switchBrand = useCallback(
    (brandId: string) => {
      setProfile((prev) => {
        if (!prev) return prev
        const membership = prev.memberships.find((m) => m.brand_id === brandId)
        if (!membership) return prev
        storeActiveBrandId(brandId)
        return { ...prev, activeMembership: membership }
      })
      clearBrandScopedQueries(queryClient)
    },
    [queryClient],
  )

  const refreshProfile = useCallback(
    async (activateBrandId?: string) => {
      try {
        const me = await apiFetch<Me>('/api/v1/me')
        if (activateBrandId && me.memberships.some((m) => m.brand_id === activateBrandId)) {
          storeActiveBrandId(activateBrandId)
          clearBrandScopedQueries(queryClient)
        }
        setProfile(toProfile(me))
      } catch {
        // Token ya validado recientemente; un fallo aquí es inesperado pero no
        // amerita forzar logout -- el caller puede reintentar si lo necesita.
      }
    },
    [queryClient],
  )

  const signOut = useCallback(async () => {
    clearBrandScopedQueries(queryClient)
    setApiAuthToken(null)
    setProfile(null)
    setAuthError(null)
    setStatus('anonymous')
    if (supabaseClient) {
      await supabaseClient.auth.signOut()
    }
  }, [supabaseClient, queryClient])

  const value = useMemo(
    () => ({
      status,
      profile,
      authError,
      signInWithPassword,
      signOut,
      refreshProfile,
      switchBrand,
    }),
    [status, profile, authError, signInWithPassword, signOut, refreshProfile, switchBrand],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
