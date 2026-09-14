import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import { ApprovalsQueuePage } from './ApprovalsQueuePage'
import type { QueueOut } from './types'

// Solo se simula la capa de red (`apiFetch`); ApiError y el cliente
// permanecen reales. Sin llamadas de red, sin datos ficticios renderizados.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const fetchMock = vi.mocked(apiFetch)

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

function sessionFor(role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER'): SessionContextValue {
  return {
    status: 'authenticated',
    profile: {
      displayName: 'Kinu Reviewer',
      email: null,
      memberships: [{ brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role }],
      activeMembership: { brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role },
    },
    selectedRole: 'content_reviewer',
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
}

function renderPage(role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionFor(role)}>
        <MemoryRouter>
          <ApprovalsQueuePage />
        </MemoryRouter>
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('ApprovalsQueuePage', () => {
  it('oculta la cola para Creator sin llamar a la API', () => {
    renderPage('CREATOR')
    expect(screen.getByText('Approvals es solo para Content Reviewer')).toBeDefined()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('oculta la cola para Visual Reviewer sin llamar a la API', () => {
    renderPage('VISUAL_REVIEWER')
    expect(screen.getByText('Approvals es solo para Content Reviewer')).toBeDefined()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('muestra el estado de carga para Content Reviewer', async () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderPage('CONTENT_REVIEWER')
    expect(await screen.findByText('Cargando cola de revisión…')).toBeDefined()
  })

  it('muestra el estado vacío cuando no hay nada pendiente', async () => {
    fetchMock.mockResolvedValue({ items: [] } satisfies QueueOut)
    renderPage('CONTENT_REVIEWER')
    expect(await screen.findByText('Nada pendiente de revisión')).toBeDefined()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/content-reviews/queue')
  })

  it('muestra el estado de permiso ante un 403 del backend', async () => {
    fetchMock.mockRejectedValueOnce(new ApiError('denied', 403, 'PERMISSION_DENIED'))
    renderPage('CONTENT_REVIEWER')
    expect(await screen.findByText('No tienes acceso a esta marca')).toBeDefined()
  })

  it('lista ítems reales de la cola con tipo y versión enviada', async () => {
    fetchMock.mockResolvedValue({
      items: [
        {
          item: {
            id: 'item-1',
            brand_id: 'brand-1',
            type: 'PRODUCT_DESCRIPTION',
            title: 'Quinoa Bites Product Description',
            workflow_status: 'PENDING_CONTENT_REVIEW',
            created_by: 'user-1',
            created_at: '2026-09-13T12:00:00Z',
            updated_at: '2026-09-13T12:00:00Z',
            latest_version: 2,
          },
          submitted_version: {
            id: 'version-2',
            creative_item_id: 'item-1',
            version: 2,
            origin: 'HUMAN_EDIT',
            brand_dna_version_id: null,
            consistency_score: null,
            created_by: 'user-1',
            created_at: '2026-09-13T12:05:00Z',
          },
          submitted_at: '2026-09-13T12:05:00Z',
        },
      ],
    } satisfies QueueOut)
    renderPage('CONTENT_REVIEWER')

    expect(await screen.findByText('Quinoa Bites Product Description')).toBeDefined()
    expect(screen.getByText(/v2/)).toBeDefined()
  })
})
