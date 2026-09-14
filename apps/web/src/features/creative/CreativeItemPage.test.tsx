import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import { ApiError, apiFetch } from '../../shared/api/client'
import { CreativeItemPage } from './CreativeItemPage'
import type { ItemOut, VersionList, VersionOut, AppliedContextOut } from './types'

// Solo se simula la capa de red; el manejo de errores por código de envelope
// (503 KNOWLEDGE_NOT_AVAILABLE, 409 INVALID_WORKFLOW_TRANSITION) es real.
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
    membership: {
      brand_id: 'brand-1',
      brand_name: 'Kinu',
      brand_slug: 'kinu',
      role: 'CREATOR',
    },
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
}

const item: ItemOut = {
  id: 'item-1',
  brand_id: 'brand-1',
  type: 'PRODUCT_DESCRIPTION',
  title: 'Quinoa Bites Product Description',
  workflow_status: 'DRAFT',
  created_by: 'user-1',
  created_at: '2026-09-13T12:00:00Z',
  updated_at: '2026-09-13T12:00:00Z',
  latest_version: 2,
  current_version: {
    id: 'v-2',
    creative_item_id: 'item-1',
    version: 2,
    origin: 'AI_GENERATED',
    brand_dna_version_id: 'dna-1',
    consistency_score: null,
    created_by: 'user-1',
    created_at: '2026-09-13T12:00:00Z',
    brief: { objective: 'Introduce Quinoa Bites.' },
    output: {
      content_type: 'product_description',
      title: 'Quinoa Bites Product Description',
      content: 'Un snack moderno y natural.',
      structured_sections: null,
      applied_rule_ids: ['rule-1'],
    },
    applied_rule_ids: ['rule-1'],
    consistency_result: null,
    langfuse_trace_id: 'trace-1',
  },
}

const versions: VersionList = {
  versions: [
    {
      id: 'v-1',
      creative_item_id: 'item-1',
      version: 1,
      origin: 'HUMAN_EDIT',
      brand_dna_version_id: null,
      consistency_score: null,
      created_by: 'user-1',
      created_at: '2026-09-13T11:00:00Z',
    },
    {
      id: 'v-2',
      creative_item_id: 'item-1',
      version: 2,
      origin: 'AI_GENERATED',
      brand_dna_version_id: 'dna-1',
      consistency_score: null,
      created_by: 'user-1',
      created_at: '2026-09-13T12:00:00Z',
    },
  ],
}

const appliedContext: AppliedContextOut = {
  creative_item_id: 'item-1',
  version_id: 'v-2',
  version: 2,
  brand_dna_version_id: 'dna-1',
  applied_rule_ids: ['rule-1'],
}

const versionDetail: VersionOut = {
  id: 'v-1',
  creative_item_id: 'item-1',
  version: 1,
  origin: 'HUMAN_EDIT',
  brand_dna_version_id: null,
  consistency_score: null,
  created_by: 'user-1',
  created_at: '2026-09-13T11:00:00Z',
  brief: { objective: 'Introduce Quinoa Bites.' },
  output: {
    content_type: 'product_description',
    title: 'Borrador manual',
    content: 'Borrador manual guardado como primera edición humana.',
    structured_sections: null,
    applied_rule_ids: [],
  },
  applied_rule_ids: [],
  consistency_result: null,
  langfuse_trace_id: null,
}

/** Despacha las lecturas del item page; las mutaciones se mockean por test. */
function mockReads() {
  fetchMock.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      throw new Error(`unexpected POST ${path}`)
    }
    switch (true) {
      case path === '/api/v1/creative-items/item-1':
        return item
      case path === '/api/v1/creative-items/item-1/versions':
        return versions
      case path === '/api/v1/creative-items/item-1/versions/v-1':
        return versionDetail
      case path === '/api/v1/creative-items/item-1/applied-context':
        return appliedContext
      case path === '/api/v1/brands/brand-1/brand-dna':
        return { active: { id: 'dna-1', version: 3 }, draft: null }
      default:
        throw new Error(`unexpected GET ${path}`)
    }
  })
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={sessionValue}>
        <MemoryRouter initialEntries={['/creative/items/item-1']}>
          <Routes>
            <Route path="/creative/items/:itemId" element={<CreativeItemPage />} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('CreativeItemPage (estados de error por envelope)', () => {
  it('presenta el 503 KNOWLEDGE_NOT_AVAILABLE como estado claro, sin CTA inventada', async () => {
    mockReads()
    renderPage()
    // Esperar a que todas las queries de lectura resuelvan antes de encolar
    // el error (el mock `Once` se consumiría por un GET rezagado).
    expect(await screen.findByText('Un snack moderno y natural.')).toBeDefined()
    expect(await screen.findByText('Edición humana')).toBeDefined()
    expect(await screen.findByText(/1 reglas recuperadas/)).toBeDefined()

    fetchMock.mockRejectedValueOnce(
      new ApiError('Brand Knowledge is OUTDATED; SYNCED is required', 503, 'KNOWLEDGE_NOT_AVAILABLE'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Regenerar con IA' }))

    expect(
      await screen.findByText(/Brand Knowledge no está sincronizado para esta marca/),
    ).toBeDefined()
  })

  it('presenta el 409 INVALID_WORKFLOW_TRANSITION al enviar desde un estado no autorable', async () => {
    mockReads()
    renderPage()
    expect(await screen.findByText('Un snack moderno y natural.')).toBeDefined()
    expect(await screen.findByText('Edición humana')).toBeDefined()
    expect(await screen.findByText(/1 reglas recuperadas/)).toBeDefined()

    // La siguiente llamada de red (el POST de submit) responde 409.
    fetchMock.mockRejectedValueOnce(
      new ApiError(
        'Creative item cannot be submitted from its current state',
        409,
        'INVALID_WORKFLOW_TRANSITION',
      ),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Enviar a revisión' }))
    fireEvent.click(screen.getByRole('button', { name: /Confirmar envío de v2/ }))

    await waitFor(() => {
      expect(screen.getByText(/Transición inválida:/)).toBeDefined()
    })
    expect(
      screen.getByText(/Creative item cannot be submitted from its current state/),
    ).toBeDefined()
  })

  it('muestra el contexto aplicado real (versión Brand DNA + reglas) y el historial', async () => {
    mockReads()
    renderPage()

    expect(await screen.findByText('Contexto aplicado')).toBeDefined()
    expect(screen.getByText(/versión activa v3/)).toBeDefined()
    expect(screen.getByText(/1 reglas recuperadas/)).toBeDefined()
    expect(screen.getByText('Edición humana')).toBeDefined()
    expect(screen.getByText('vigente')).toBeDefined()
  })

  it('abre una versión previa del historial como detalle read-only', async () => {
    mockReads()
    renderPage()
    expect(await screen.findByText('Un snack moderno y natural.')).toBeDefined()

    fireEvent.click(screen.getByRole('button', { name: 'Ver versión 1' }))

    expect(await screen.findByText('Borrador manual guardado como primera edición humana.')).toBeDefined()
    expect(screen.getByText('Versión v1 · Edición humana')).toBeDefined()
    // Sin versión de Brand DNA asociada: edición humana sin recuperación RAG.
    expect(screen.getByText(/sin versión de Brand DNA asociada/)).toBeDefined()
  })
})
