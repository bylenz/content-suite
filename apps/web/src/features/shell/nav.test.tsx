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

function sessionWith(
  role: Membership['role'],
  extraMemberships: Membership[] = [],
  switchBrand: (brandId: string) => void = () => {},
): SessionContextValue {
  const active = membership(role)
  return {
    status: 'authenticated',
    profile: {
      displayName: 'Kinu Dev',
      email: null,
      memberships: [active, ...extraMemberships],
      activeMembership: active,
    },
    selectedRole: null,
    availableDevRoles: [],
    authenticate: () => {},
    switchRole: () => {},
    nextDevRole: null,
    authError: null,
    signInWithMagicLink: async () => null,
    signOut: async () => {},
    refreshProfile: async () => {},
    switchBrand,
  }
}

function renderSidebar(
  role: Membership['role'],
  extraMemberships: Membership[] = [],
  switchBrand?: (brandId: string) => void,
) {
  return render(
    <MemoryRouter>
      <SessionContext.Provider value={sessionWith(role, extraMemberships, switchBrand)}>
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

describe('conmutador de workspace', () => {
  it('muestra el nombre como texto plano cuando la identidad pertenece a una sola marca', () => {
    renderSidebar('CREATOR')
    expect(screen.queryByLabelText('Cambiar de workspace')).toBeNull()
    expect(screen.getByText('Kinu')).toBeDefined()
  })

  it('ofrece un selector con todas las marcas cuando hay más de una membresía', () => {
    const second: Membership = {
      brand_id: 'brand-2',
      brand_name: 'Segunda Marca',
      brand_slug: 'segunda-marca',
      role: 'CREATOR',
    }
    renderSidebar('CREATOR', [second])

    const select = screen.getByLabelText('Cambiar de workspace') as HTMLSelectElement
    expect(select.value).toBe('brand-1')
    expect(screen.getByRole('option', { name: 'Kinu' })).toBeDefined()
    expect(screen.getByRole('option', { name: 'Segunda Marca' })).toBeDefined()
  })

  it('llama a switchBrand con el brand_id elegido', () => {
    const second: Membership = {
      brand_id: 'brand-2',
      brand_name: 'Segunda Marca',
      brand_slug: 'segunda-marca',
      role: 'CREATOR',
    }
    const switchBrand = vi.fn()
    renderSidebar('CREATOR', [second], switchBrand)

    const select = screen.getByLabelText('Cambiar de workspace') as HTMLSelectElement
    select.value = 'brand-2'
    select.dispatchEvent(new Event('change', { bubbles: true }))

    expect(switchBrand).toHaveBeenCalledWith('brand-2')
  })
})
