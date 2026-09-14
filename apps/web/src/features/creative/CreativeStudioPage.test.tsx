import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import { CreativeStudioPage } from './CreativeStudioPage'
import type { ItemList } from './types'

// Solo se simula la capa de red (`apiFetch`); ApiError y el cliente
// permanecen reales. Sin llamadas de red, sin datos ficticios renderizados.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const fetchMock = vi.mocked(apiFetch)

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

const sessionValue: SessionContextValue = {
  status: 'authenticated',
  profile: {
    displayName: 'Kinu Creator',
    email: null,
    memberships: [{ brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role: 'CREATOR' }],
    activeMembership: { brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role: 'CREATOR' },
  },
  selectedRole: 'creator',
  availableDevRoles: [],
  authenticate: () => {},
  switchRole: () => {},
  nextDevRole: null,
  authError: null,
  signInWithPassword: async () => null,
  signOut: async () => {},
  refreshProfile: async () => {},
  switchBrand: () => {},
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionValue}>
        <MemoryRouter>
          <CreativeStudioPage />
        </MemoryRouter>
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('CreativeStudioPage', () => {
  it('muestra el estado de carga', async () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(await screen.findByText('Cargando Creative Studio…')).toBeDefined()
  })

  it('muestra el estado vacío cuando la marca no tiene ítems', async () => {
    fetchMock.mockResolvedValue({ items: [] } satisfies ItemList)
    renderPage()
    expect(await screen.findByText('Aún no hay contenido')).toBeDefined()
    // La consulta porta la marca de la sesión.
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/creative-items?brand_id=brand-1')
  })

  it('muestra el estado de permiso ante un 403 del backend', async () => {
    fetchMock.mockRejectedValueOnce(new ApiError('denied', 403, 'PERMISSION_DENIED'))
    renderPage()
    expect(await screen.findByText('No tienes acceso a esta marca')).toBeDefined()
  })

  it('muestra el estado de error con reintento', async () => {
    fetchMock.mockRejectedValueOnce(new Error('API caída'))
    renderPage()
    expect(await screen.findByText('No se pudo cargar el contenido')).toBeDefined()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeDefined()
  })

  it('lista ítems reales con tipo, versión y estado de workflow', async () => {
    fetchMock.mockResolvedValue({
      items: [
        {
          id: 'item-1',
          brand_id: 'brand-1',
          type: 'PRODUCT_DESCRIPTION',
          title: 'Quinoa Bites Product Description',
          workflow_status: 'DRAFT',
          created_by: 'user-1',
          created_at: '2026-09-13T12:00:00Z',
          updated_at: '2026-09-13T12:00:00Z',
          latest_version: 2,
        },
      ],
    } satisfies ItemList)
    renderPage()

    expect(await screen.findByText('Quinoa Bites Product Description')).toBeDefined()
    expect(screen.getByText('Borrador')).toBeDefined()
    expect(screen.getByText(/v2/)).toBeDefined()
  })
})
