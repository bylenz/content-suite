import type { DemoRole } from '../session/roles'

export type NavSectionGroup = 'WORKSPACE' | 'BRAND' | 'CREATE' | 'GOVERNANCE'

export interface NavItem {
  id: string
  label: string
  group: NavSectionGroup
  /** Ruta cuando la sección ya está implementada; undefined = change futura */
  to?: string
}

/**
 * Navegación por rol según docs/UI_UX.md. Solo Dashboard tiene ruta en la
 * foundation; el resto se lista deshabilitado hasta su change correspondiente.
 */
export const NAV_ITEMS: Record<DemoRole, NavItem[]> = {
  creator: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND' },
    { id: 'creative-studio', label: 'Creative Studio', group: 'CREATE' },
  ],
  content_reviewer: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND' },
    { id: 'approvals', label: 'Approvals', group: 'GOVERNANCE' },
  ],
  visual_reviewer: [
    { id: 'dashboard', label: 'Dashboard', group: 'WORKSPACE', to: '/' },
    { id: 'brand-dna', label: 'Brand DNA', group: 'BRAND' },
    { id: 'brand-audit', label: 'Brand Audit', group: 'GOVERNANCE' },
  ],
}

export function groupNavItems(items: NavItem[]): { group: NavSectionGroup; items: NavItem[] }[] {
  const order: NavSectionGroup[] = ['WORKSPACE', 'BRAND', 'CREATE', 'GOVERNANCE']
  return order
    .map((group) => ({ group, items: items.filter((item) => item.group === group) }))
    .filter((entry) => entry.items.length > 0)
}
