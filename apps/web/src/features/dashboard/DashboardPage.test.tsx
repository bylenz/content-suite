import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import type { ActivityListResponse, BrandDnaOverview, PipelineOut } from '../../shared/api/types'
import { DashboardPage } from './DashboardPage'

// Solo se simula la capa de red (`apiFetch`): DashboardPage dispara cuatro
// consultas (health, brand-dna, pipeline, activity) que se enrutan por URL,
// sin datos ficticios renderizados fuera de lo que cada mock entrega.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const fetchMock = vi.mocked(apiFetch)

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

const EMPTY_DNA: BrandDnaOverview = { active: null, draft: null }
const EMPTY_PIPELINE: PipelineOut = {
  brand_id: 'brand-1',
  counts: {
    DRAFT: 0,
    PENDING_CONTENT_REVIEW: 0,
    CONTENT_CHANGES_REQUESTED: 0,
    CONTENT_APPROVED: 0,
    PENDING_VISUAL_REVIEW: 0,
    VISUAL_CHANGES_REQUESTED: 0,
    FINAL_APPROVED: 0,
  },
  total: 0,
}
const EMPTY_ACTIVITY: ActivityListResponse = { items: [], total: 0 }

function sessionFor(role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER'): SessionContextValue {
  return {
    status: 'authenticated',
    profile: {
      displayName: 'Kinu Creator',
      email: null,
      memberships: [{ brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role }],
      activeMembership: { brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role },
    },
    selectedRole: 'creator',
    availableDevRoles: [],
    authenticate: () => {},
    switchRole: () => {},
    nextDevRole: null,
    authError: null,
    signInWithMagicLink: async () => null,
    signOut: async () => {},
    refreshProfile: async () => {},
    switchBrand: () => {},
  }
}

/** Enruta `apiFetch` por URL: cada endpoint del dashboard responde por separado. */
function routeApi(responses: {
  health?: unknown
  brandDna?: unknown
  pipeline?: unknown | (() => Promise<unknown>)
  activity?: unknown | (() => Promise<unknown>)
}) {
  fetchMock.mockImplementation(async (url: string) => {
    if (url.startsWith('/health/ready')) return responses.health ?? { status: 'ok' }
    if (url.includes('/creative-items/pipeline')) {
      const value = responses.pipeline ?? EMPTY_PIPELINE
      return typeof value === 'function' ? await (value as () => Promise<unknown>)() : value
    }
    if (url.includes('/api/v1/activity')) {
      const value = responses.activity ?? EMPTY_ACTIVITY
      return typeof value === 'function' ? await (value as () => Promise<unknown>)() : value
    }
    if (url.includes('/brand-dna')) return responses.brandDna ?? EMPTY_DNA
    throw new Error(`unexpected url in test: ${url}`)
  })
}

function renderDashboard(role: 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER' = 'CREATOR') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionFor(role)}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('DashboardPage — Content Pipeline widget', () => {
  it('muestra el estado de carga diferenciado', async () => {
    routeApi({ pipeline: () => new Promise(() => {}) })
    renderDashboard()
    expect(await screen.findByText('Consultando el pipeline de contenido…')).toBeDefined()
  })

  it('muestra el estado de error con reintento', async () => {
    routeApi({ pipeline: () => Promise.reject(new Error('API caída')) })
    renderDashboard()
    expect(await screen.findByText('API caída')).toBeDefined()
    expect(screen.getAllByRole('button', { name: 'Reintentar' }).length).toBeGreaterThan(0)
  })

  it('muestra el estado de permiso ante un 403 del backend', async () => {
    routeApi({ pipeline: () => Promise.reject(new ApiError('denied', 403, 'PERMISSION_DENIED')) })
    renderDashboard()
    expect(await screen.findByText('Tu identidad no tiene acceso a esta marca.')).toBeDefined()
  })

  it('muestra el estado vacío real (sin items) para una marca sin creative items', async () => {
    routeApi({ pipeline: EMPTY_PIPELINE })
    renderDashboard()
    expect(
      await screen.findByText(/Todavía no hay creative items en esta marca/),
    ).toBeDefined()
  })

  it('expone los 7 estados reales con cero explícito y resalta el subconjunto del rol', async () => {
    const pipeline: PipelineOut = {
      brand_id: 'brand-1',
      counts: {
        DRAFT: 2,
        PENDING_CONTENT_REVIEW: 3,
        CONTENT_CHANGES_REQUESTED: 0,
        CONTENT_APPROVED: 1,
        PENDING_VISUAL_REVIEW: 0,
        VISUAL_CHANGES_REQUESTED: 0,
        FINAL_APPROVED: 4,
      },
      total: 10,
    }
    routeApi({ pipeline })
    renderDashboard('CONTENT_REVIEWER')

    // Los 7 estados reales están presentes, nunca una simplificación de 4 categorías.
    expect(await screen.findByText('Borrador')).toBeDefined()
    expect(screen.getByText('Pendiente revisión de contenido')).toBeDefined()
    expect(screen.getByText('Cambios de contenido solicitados')).toBeDefined()
    expect(screen.getByText('Contenido aprobado')).toBeDefined()
    expect(screen.getByText('Pendiente revisión visual')).toBeDefined()
    expect(screen.getByText('Cambios visuales solicitados')).toBeDefined()
    expect(screen.getByText('Aprobado final')).toBeDefined()
    expect(screen.getByText('10 items')).toBeDefined()

    // Content Reviewer resalta PENDING_CONTENT_REVIEW (design.md).
    const highlighted = screen.getByText('Pendiente revisión de contenido').closest('li')
    expect(highlighted?.className).toContain('bg-tint-steel')
    const notHighlighted = screen.getByText('Borrador').closest('li')
    expect(notHighlighted?.className).not.toContain('bg-tint-steel')
  })
})

describe('DashboardPage — Recent Activity widget', () => {
  it('muestra el estado de carga diferenciado', async () => {
    routeApi({ activity: () => new Promise(() => {}) })
    renderDashboard()
    expect(await screen.findByText('Consultando la actividad reciente…')).toBeDefined()
  })

  it('muestra el estado de error con reintento', async () => {
    routeApi({ activity: () => Promise.reject(new Error('API caída')) })
    renderDashboard()
    expect(await screen.findByText('API caída')).toBeDefined()
  })

  it('muestra el estado vacío real (sin eventos) para una marca sin actividad', async () => {
    routeApi({ activity: EMPTY_ACTIVITY })
    renderDashboard()
    expect(
      await screen.findByText(/Todavía no hay actividad registrada en esta marca/),
    ).toBeDefined()
  })

  it('renderiza eventos reales fusionados y expone el total', async () => {
    const activity: ActivityListResponse = {
      items: [
        {
          id: 'evt-1',
          source: 'WORKFLOW_EVENT',
          event_type: 'SUBMITTED',
          actor_id: 'user-1',
          created_at: '2026-09-14T10:00:00Z',
          creative_item_id: 'item-1',
          brand_dna_version_id: null,
          metadata: {},
        },
        {
          id: 'evt-2',
          source: 'BRAND_DNA_PUBLISHED',
          event_type: 'PUBLISHED',
          actor_id: 'user-2',
          created_at: '2026-09-14T09:00:00Z',
          creative_item_id: null,
          brand_dna_version_id: 'version-1',
          metadata: { version: 1 },
        },
      ],
      total: 2,
    }
    routeApi({ activity })
    renderDashboard()

    expect(await screen.findByText('Contenido enviado a revisión')).toBeDefined()
    expect(screen.getByText('Brand DNA publicado')).toBeDefined()
  })

  it('pagina cuando el total excede el tamaño de página del widget', async () => {
    const makeItem = (i: number): ActivityListResponse['items'][number] => ({
      id: `evt-${i}`,
      source: 'WORKFLOW_EVENT',
      event_type: 'SUBMITTED',
      actor_id: 'user-1',
      created_at: `2026-09-1${i}T10:00:00Z`,
      creative_item_id: 'item-1',
      brand_dna_version_id: null,
      metadata: {},
    })
    routeApi({ activity: { items: [makeItem(1), makeItem(2)], total: 7 } })
    renderDashboard()

    expect(await screen.findByText('Página 1 de 2')).toBeDefined()
    expect(screen.getByRole('button', { name: '← Anterior' })).toHaveProperty('disabled', true)
    expect(screen.getByRole('button', { name: 'Siguiente →' })).toHaveProperty('disabled', false)
  })
})
