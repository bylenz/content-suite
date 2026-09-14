import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
    authError: null,
    signInWithPassword: async () => null,
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

// Radix Popper mide el disparador con ResizeObserver; jsdom no lo trae.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
Element.prototype.scrollIntoView = () => {}

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
  const second: Membership = {
    brand_id: 'brand-2',
    brand_name: 'Segunda Marca',
    brand_slug: 'segunda-marca',
    role: 'CONTENT_REVIEWER',
  }

  it('muestra un chip estático (sin desplegable) cuando la identidad pertenece a una sola marca', () => {
    renderSidebar('CREATOR')
    expect(screen.queryByRole('button', { name: 'Cambiar de workspace' })).toBeNull()
    expect(screen.getByText('Kinu')).toBeDefined()
  })

  it('con dos o más membresías, el chip despliega todas las marcas con su rol y la activa marcada', () => {
    renderSidebar('CREATOR', [second])

    const trigger = screen.getByRole('button', { name: 'Cambiar de workspace' })
    expect(trigger.textContent).toContain('Kinu')
    expect(trigger.textContent).toContain('2 marcas')

    fireEvent.keyDown(trigger, { key: 'Enter' })

    const options = screen.getAllByRole('menuitemradio')
    expect(options.map((option) => option.textContent)).toEqual([
      expect.stringContaining('Kinu'),
      expect.stringContaining('Segunda Marca'),
    ])
    expect(options[0].getAttribute('aria-checked')).toBe('true')
    expect(options[1].getAttribute('aria-checked')).toBe('false')
    expect(options[1].textContent).toContain('Content Reviewer')
  })

  it('llama a switchBrand con el brand_id elegido y no al reelegir la activa', () => {
    const switchBrand = vi.fn()
    renderSidebar('CREATOR', [second], switchBrand)
    const trigger = screen.getByRole('button', { name: 'Cambiar de workspace' })

    fireEvent.keyDown(trigger, { key: 'Enter' })
    fireEvent.click(screen.getByRole('menuitemradio', { name: /Segunda Marca/ }))
    expect(switchBrand).toHaveBeenCalledWith('brand-2')

    fireEvent.keyDown(trigger, { key: 'Enter' })
    fireEvent.click(screen.getByRole('menuitemradio', { name: /Kinu/ }))
    expect(switchBrand).toHaveBeenCalledTimes(1)
  })
})

describe('alta de workspace y sesión real', () => {
  it('ofrece el enlace "Nuevo workspace" hacia /workspaces/new', () => {
    renderSidebar('CREATOR')
    const link = screen.getByRole('link', { name: /Nuevo workspace/ }) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/workspaces/new')
  })

  it('no muestra ningún conmutador de identidad de prueba', () => {
    renderSidebar('CREATOR')
    expect(screen.queryByText(/\(dev\)/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeDefined()
  })
})
