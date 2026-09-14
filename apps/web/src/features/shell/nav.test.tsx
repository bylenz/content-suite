import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { SessionContext, type SessionContextValue } from '../session/session-context'
import type { Membership } from '../../shared/api/types'
import { NAV_ITEMS } from './nav'
import { SidebarContent } from './SidebarContent'

// Sin red: la nav se decide con el rol resuelto por la sesión (`/api/v1/me`).
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

function membership(role: Membership['role']): Membership {
  return { brand_id: 'brand-1', brand_name: 'Kinu', brand_slug: 'kinu', role }
}

function sessionWith(role: Membership['role']): SessionContextValue {
  return {
    status: 'authenticated',
    profile: { displayName: 'Kinu Dev', email: null, membership: membership(role) },
    selectedRole: null,
    availableDevRoles: [],
    authenticate: () => {},
    switchRole: () => {},
    nextDevRole: null,
    authError: null,
    signInWithMagicLink: async () => null,
    signOut: async () => {},
  }
}

function renderSidebar(role: Membership['role']) {
  return render(
    <MemoryRouter>
      <SessionContext.Provider value={sessionWith(role)}>
        <SidebarContent />
      </SessionContext.Provider>
    </MemoryRouter>,
  )
}

afterEach(cleanup)

describe('navegación Creative Studio', () => {
  it('queda habilitada para el Creator ahora que el contrato existe (ruta /creative)', () => {
    const creatorItems = NAV_ITEMS.CREATOR
    const creative = creatorItems.find((item) => item.id === 'creative-studio')
    expect(creative?.to).toBe('/creative')
  })

  it('se renderiza como enlace activo (sin etiqueta Próximamente) para el Creator', () => {
    renderSidebar('CREATOR')
    const link = screen.getByRole('link', { name: /Creative Studio/ }) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/creative')
    // El ítem habilitado nunca lleva la etiqueta de change futura.
    expect(screen.queryByText('Próximamente')).toBeNull()
  })

  it('no aparece para revisores: su acceso de lectura llega con la change de governance', () => {
    renderSidebar('CONTENT_REVIEWER')
    expect(screen.queryByText('Creative Studio')).toBeNull()
    renderSidebar('VISUAL_REVIEWER')
    expect(screen.queryByText('Creative Studio')).toBeNull()
  })
})
