import type { BrandRole } from '../../shared/api/types'

export type NavSectionGroup = 'WORKSPACE' | 'BRAND' | 'CREATE' | 'GOVERNANCE' | 'SYSTEM'

export interface NavItem {
  id: string
  label: string
  group: NavSectionGroup
  /** Ruta cuando la sección ya está implementada; undefined = change futura */
  to?: string
}

/**
 * Navegación por rol según docs/UI_UX.md, con el rol resuelto por el backend
 * (`/api/v1/me`). Dashboard, Brand DNA, Creative Studio y Observability
 * tienen ruta; el resto se lista deshabilitado hasta su change correspondiente.
 * Brand DNA es lectura para revisores y Observability es solo lectura para
 * los tres roles (metadatos sanitizados de sus marcas): la interfaz oculta
 * los controles de escritura, pero la autoridad vive en el backend.
 */
export const NAV_ITEMS: Record<BrandRole, NavItem[]> = {
  CREATOR: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND', to: '/brand-dna' },
    { id: 'creative-studio', label: 'Creative Studio', group: 'CREATE', to: '/creative' },
    { id: 'observability', label: 'Observability', group: 'SYSTEM', to: '/observability' },
  ],
  CONTENT_REVIEWER: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND', to: '/brand-dna' },
    { id: 'approvals', label: 'Approvals', group: 'GOVERNANCE', to: '/approvals' },
    { id: 'observability', label: 'Observability', group: 'SYSTEM', to: '/observability' },
  ],
  VISUAL_REVIEWER: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND', to: '/brand-dna' },
    { id: 'brand-audit', label: 'Brand Audit', group: 'GOVERNANCE' },
    { id: 'observability', label: 'Observability', group: 'SYSTEM', to: '/observability' },
  ],
}

export function groupNavItems(items: NavItem[]): { group: NavSectionGroup; items: NavItem[] }[] {
  const order: NavSectionGroup[] = ['WORKSPACE', 'BRAND', 'CREATE', 'GOVERNANCE', 'SYSTEM']
  return order
    .map((group) => ({ group, items: items.filter((item) => item.group === group) }))
    .filter((entry) => entry.items.length > 0)
}
