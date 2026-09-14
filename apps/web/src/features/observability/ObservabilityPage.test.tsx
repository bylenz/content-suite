import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import type { TraceRecord } from '../../shared/api/types'
import { ObservabilityPage } from './ObservabilityPage'

// Solo se simula la capa de red (`apiFetch`); ApiError y el resto del cliente
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
  signInWithMagicLink: async () => null,
  signOut: async () => {},
  refreshProfile: async () => {},
  switchBrand: () => {},
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionValue}>
        <ObservabilityPage />
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

function makeTrace(overrides: Partial<TraceRecord> = {}): TraceRecord {
  return {
    trace_id: 'trace-abc-123',
    brand_id: 'brand-1',
    entity_type: 'brand_dna_version',
    entity_id: '11111111-1111-1111-1111-111111111111',
    operation: 'brand.architect',
    prompt_version: 'brand.architect.v1',
    model: 'fake-text-model',
    latency_ms: 1234.5,
    outcome: 'ok',
    error_type: null,
    created_at: '2026-09-13T12:00:00Z',
    ...overrides,
  }
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('ObservabilityPage', () => {
  it('muestra el estado de carga diferenciado', async () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(await screen.findByText('Cargando traces…')).toBeDefined()
  })

  it('muestra el estado de error con reintento', async () => {
    fetchMock.mockRejectedValueOnce(new Error('API caída'))
    renderPage()
    expect(await screen.findByText('No se pudieron cargar los traces')).toBeDefined()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeDefined()
  })

  it('muestra el estado de permiso ante un 403 del backend', async () => {
    fetchMock.mockRejectedValueOnce(new ApiError('denied', 403, 'PERMISSION_DENIED'))
    renderPage()
    expect(await screen.findByText('No tienes acceso a esta marca')).toBeDefined()
  })

  it('muestra el estado vacío cuando no hay traces', async () => {
    fetchMock.mockResolvedValue({ items: [], total: 0, langfuse_configured: true })
    renderPage()
    expect(await screen.findByText('Sin traces todavía')).toBeDefined()
  })

  it('renderiza traces reales, consulta la marca propia y muestra el banner sin Langfuse', async () => {
    fetchMock.mockResolvedValue({
      items: [
        makeTrace(),
        makeTrace({
          trace_id: 'trace-def-456',
          operation: 'consistency.text',
          outcome: 'error',
          error_type: 'AIOutputValidationError',
        }),
      ],
      total: 2,
      langfuse_configured: false,
    })
    renderPage()

    expect(await screen.findByText('brand.architect')).toBeDefined()
    expect(screen.getByText('consistency.text')).toBeDefined()

    // Filtro por marca propia: la query siempre porta el brand de la sesión.
    expect(fetchMock).toHaveBeenCalled()
    const url = fetchMock.mock.calls[0]?.[0] ?? ''
    expect(url).toContain('brand_id=brand-1')
    expect(url).toContain('/api/v1/traces?')

    // Banner explícito de estado sin Langfuse (spec 07).
    expect(screen.getByText(/Langfuse no está configurado/)).toBeDefined()
  })

  it('aplica el filtro por tipo de entidad en la consulta', async () => {
    fetchMock.mockResolvedValue({ items: [], total: 0, langfuse_configured: true })
    renderPage()
    await screen.findByText('Sin traces todavía')

    fireEvent.change(screen.getByLabelText('Filtrar por tipo de entidad'), {
      target: { value: 'brand_dna_version' },
    })

    await waitFor(() => {
      const url = fetchMock.mock.calls.at(-1)?.[0] ?? ''
      expect(url).toContain('entity_type=brand_dna_version')
    })
  })

  it('renderiza el detalle solo con campos del allowlist (sin datos crudos)', async () => {
    fetchMock.mockResolvedValueOnce({ items: [makeTrace()], total: 1, langfuse_configured: true })
    renderPage()
    await screen.findByText('brand.architect')

    fetchMock.mockClear()
    fetchMock.mockResolvedValueOnce(makeTrace())
    fireEvent.click(screen.getByRole('button', { name: 'Ver detalle' }))

    expect(await screen.findByText('Detalle del trace')).toBeDefined()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/traces/trace-abc-123')

    // El detalle expone exactamente los metadatos allowlist del contrato:
    // ningún campo de texto libre, prompt completo o payload crudo.
    const labels = Array.from(document.querySelectorAll('dt')).map((el) => el.textContent)
    expect(labels).toEqual([
      'Marca',
      'Entidad',
      'Operación',
      'Prompt version',
      'Modelo',
      'Latencia',
      'Outcome',
      'Fecha',
    ])
  })

  it('deshabilita el detalle de traces sin trace id (tracer no-op)', async () => {
    fetchMock.mockResolvedValue({
      items: [makeTrace({ trace_id: null })],
      total: 1,
      langfuse_configured: true,
    })
    renderPage()

    const button = (await screen.findByRole('button', { name: 'Ver detalle' })) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.getByText('sin trace id')).toBeDefined()
  })
})
