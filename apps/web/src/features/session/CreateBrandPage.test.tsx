import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { SessionContext, type SessionContextValue } from './session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import { CreateBrandPage } from './CreateBrandPage'
import type { Membership } from '../../shared/api/types'

// Solo se simula la capa de red (`apiFetch`); ApiError y el cliente
// permanecen reales. Sin llamadas de red, sin datos ficticios renderizados.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const fetchMock = vi.mocked(apiFetch)

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

function sessionWithRefresh(refreshProfile: () => Promise<void>): SessionContextValue {
  return {
    status: 'authenticated',
    profile: { displayName: 'Nuevo usuario', email: 'new@example.com', membership: null },
    selectedRole: null,
    availableDevRoles: [],
    authenticate: () => {},
    switchRole: () => {},
    nextDevRole: null,
    authError: null,
    signInWithMagicLink: async () => null,
    signOut: async () => {},
    refreshProfile,
  }
}

function renderPage(refreshProfile: () => Promise<void> = async () => {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionWithRefresh(refreshProfile)}>
        <CreateBrandPage />
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('CreateBrandPage', () => {
  it('crea el workspace con el nombre ingresado y refresca el perfil', async () => {
    const membership: Membership = {
      brand_id: 'brand-new',
      brand_name: 'Acme Foods',
      brand_slug: 'acme-foods',
      role: 'CREATOR',
    }
    fetchMock.mockResolvedValue(membership)
    const refreshProfile = vi.fn().mockResolvedValue(undefined)
    renderPage(refreshProfile)

    fireEvent.change(screen.getByPlaceholderText('Nombre de tu marca'), {
      target: { value: 'Acme Foods' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Crear workspace' }))

    await vi.waitFor(() => expect(refreshProfile).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/brands', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Acme Foods' }),
    })
  })

  it('muestra el mensaje de error del backend sin refrescar el perfil', async () => {
    fetchMock.mockRejectedValueOnce(new ApiError('El nombre ya está en uso', 409))
    const refreshProfile = vi.fn().mockResolvedValue(undefined)
    renderPage(refreshProfile)

    fireEvent.change(screen.getByPlaceholderText('Nombre de tu marca'), {
      target: { value: 'Overlap' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Crear workspace' }))

    expect(await screen.findByText('El nombre ya está en uso')).toBeDefined()
    expect(refreshProfile).not.toHaveBeenCalled()
  })

  it('deshabilita el envío con el nombre vacío', () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Crear workspace' })).toHaveProperty(
      'disabled',
      true,
    )
  })
})
