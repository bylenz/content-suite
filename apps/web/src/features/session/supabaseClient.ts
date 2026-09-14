import { createClient, type SupabaseClient } from '@supabase/supabase-js'

interface SupabaseEnv {
  readonly PROD: boolean
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_ANON_KEY?: string
}

/**
 * Builds the Supabase Auth client from Vite env vars.
 *
 * A production build without both vars fails loudly at startup instead of
 * silently shipping a login screen with no working action. A dev/test build
 * without them returns `null` so the app still boots (the magic-link form
 * degrades to a clear "not configured" message) — the same "absent config
 * -> None" convention the AI provider resolvers use on the backend.
 */
export function createSupabaseClient(env: SupabaseEnv): SupabaseClient | null {
  const url = env.VITE_SUPABASE_URL
  const anonKey = env.VITE_SUPABASE_ANON_KEY
  if (url && anonKey) {
    return createClient(url, anonKey, {
      auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
    })
  }
  if (env.PROD) {
    throw new Error(
      'VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY son obligatorias en producción: ' +
        'configúralas antes de desplegar.',
    )
  }
  return null
}

export const supabase = createSupabaseClient(import.meta.env)
