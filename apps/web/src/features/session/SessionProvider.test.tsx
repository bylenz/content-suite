import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AuthChangeEvent, Session, SupabaseClient } from '@supabase/supabase-js'
import type { Me } from '../../shared/api/types'
import { SessionProvider } from './SessionProvider'
import { useSession } from './useSession'

// Sin red: la sesión se decide con `GET /api/v1/me` simulado.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn(), setApiAuthToken: vi.fn() }
})

import { apiFetch, setApiAuthToken } from '../../shared/api/client'

type Listener = (event: AuthChangeEvent, session: Session | null) => void

function fakeSession(overrides: Partial<Session> = {}): Session {
  return {
    access_token: 'sb-access-token',
    refresh_token: 'sb-refresh-token',
    expires_in: 3600,
    token_type: 'bearer',
    user: { id: 'user-1' },
    ...overrides,
  } as Session
}

function fakeMe(): Me {
  return {
    id: 'user-1',
    email: 'creator@kinu.example',
    display_name: 'Kinu Creator',
    memberships: [{ brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role: 'CREATOR' }],
  }
}

/** Doble mínimo del cliente Supabase: solo lo que SessionProvider usa. */
function createFakeSupabaseClient(initialSession: Session | null) {
  let listener: Listener | null = null
  const unsubscribe = vi.fn()
  const signOut = vi.fn(async () => ({ error: null }))
  const signInWithPassword = vi.fn<
    (credentials: { email: string; password: string }) => Promise<{ error: null }>
  >(async () => ({ error: null }))
  const client = {
    auth: {
      onAuthStateChange: (callback: Listener) => {
        listener = callback
        queueMicrotask(() => callback('INITIAL_SESSION', initialSession))
        return { data: { subscription: { unsubscribe } } }
      },
      signOut,
      signInWithPassword,
    },
  } as unknown as SupabaseClient
  return {
    client,
    signOut,
    signInWithPassword,
    emit: (event: AuthChangeEvent, session: Session | null) => listener?.(event, session),
  }
}

function Probe() {
  const { status, profile, signInWithPassword, signOut } = useSession()
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="email">{profile?.email ?? ''}</span>
      <button onClick={() => void signInWithPassword('user@example.com', 'secret-pass')}>
        log-in
      </button>
      <button onClick={() => void signOut()}>sign-out</button>
    </div>
  )
}

function renderWithProvider(supabaseClient: SupabaseClient | null) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionProvider supabaseClient={supabaseClient}>
        <Probe />
      </SessionProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(apiFetch).mockReset()
  vi.mocked(setApiAuthToken).mockReset()
  window.localStorage.clear()
})

afterEach(cleanup)

describe('SessionProvider con Supabase Auth', () => {
  it('sin sesión de Supabase ni identidad de dev guardada, termina anónimo', async () => {
    const { client } = createFakeSupabaseClient(null)
    renderWithProvider(client)

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'))
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('con sesión de Supabase en INITIAL_SESSION, se autentica vía GET /me', async () => {
    vi.mocked(apiFetch).mockResolvedValue(fakeMe())
    const { client } = createFakeSupabaseClient(fakeSession())
    renderWithProvider(client)

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))
    expect(screen.getByTestId('email').textContent).toBe('creator@kinu.example')
    expect(setApiAuthToken).toHaveBeenCalledWith('sb-access-token')
  })

  it('signInWithPassword delega en supabase.auth.signInWithPassword con email y contraseña', async () => {
    const { client, signInWithPassword } = createFakeSupabaseClient(null)
    renderWithProvider(client)
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'))

    screen.getByText('log-in').click()

    await waitFor(() => expect(signInWithPassword).toHaveBeenCalledTimes(1))
    expect(signInWithPassword.mock.calls[0][0]).toMatchObject({
      email: 'user@example.com',
      password: 'secret-pass',
    })
  })

  it('signOut limpia la sesión localmente y llama a supabase.auth.signOut', async () => {
    vi.mocked(apiFetch).mockResolvedValue(fakeMe())
    const { client, signOut } = createFakeSupabaseClient(fakeSession())
    renderWithProvider(client)
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))

    screen.getByText('sign-out').click()

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'))
    expect(signOut).toHaveBeenCalledTimes(1)
    expect(setApiAuthToken).toHaveBeenCalledWith(null)
  })

  it('sin cliente Supabase configurado (dev sin env vars), degrada a solo identidades de dev', async () => {
    renderWithProvider(null)

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'))
    expect(apiFetch).not.toHaveBeenCalled()
  })
})
