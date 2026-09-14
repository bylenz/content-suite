import { describe, expect, it } from 'vitest'
import { createSupabaseClient } from './supabaseClient'

describe('createSupabaseClient', () => {
  it('construye un cliente cuando ambas env vars están presentes', () => {
    const client = createSupabaseClient({
      PROD: false,
      VITE_SUPABASE_URL: 'https://example.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'anon-key',
    })
    expect(client).not.toBeNull()
    expect(client?.auth).toBeDefined()
  })

  it('lanza en producción cuando falta cualquiera de las dos env vars', () => {
    expect(() =>
      createSupabaseClient({ PROD: true, VITE_SUPABASE_URL: undefined, VITE_SUPABASE_ANON_KEY: undefined }),
    ).toThrow(/obligatorias en producción/)
    expect(() =>
      createSupabaseClient({
        PROD: true,
        VITE_SUPABASE_URL: 'https://example.supabase.co',
        VITE_SUPABASE_ANON_KEY: undefined,
      }),
    ).toThrow(/obligatorias en producción/)
  })

  it('devuelve null fuera de producción cuando faltan las env vars (dev/test sin configurar)', () => {
    const client = createSupabaseClient({ PROD: false, VITE_SUPABASE_URL: undefined, VITE_SUPABASE_ANON_KEY: undefined })
    expect(client).toBeNull()
  })
})
