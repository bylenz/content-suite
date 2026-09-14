import { NavLink } from 'react-router'
import { useSession } from '../session/useSession'
import { ROLE_LABELS, WORKSPACE_FALLBACK_NAME, type DemoRole } from '../session/roles'
import { groupNavItems, NAV_ITEMS } from './nav'
import { NavIcon } from './NavIcon'

/** Etiqueta de la identidad de dev para el conmutador (solo presentación). */
const DEMO_ROLE_LABELS: Record<DemoRole, string> = {
  creator: 'Creator',
  content_reviewer: 'Content Reviewer',
  visual_reviewer: 'Visual Compliance Reviewer',
}

/**
 * Sidebar persistente y elevada, con navegación azul acolchada por rol.
 * La identidad y el rol provienen de `/api/v1/me`; el conmutador de identidad
 * de dev solo selecciona el token adjunto. Las secciones sin change
 * implementada se listan deshabilitadas.
 */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { profile, switchRole, availableDevRoles, nextDevRole, signOut } = useSession()
  const role = profile?.membership?.role
  const navItems = role ? NAV_ITEMS[role] : Object.values(NAV_ITEMS)[0]
  const grouped = groupNavItems(navItems)
  const workspaceName = profile?.membership?.brand_name ?? WORKSPACE_FALLBACK_NAME

  return (
    <div className="flex h-full min-h-0 flex-col gap-1 p-3.5">
      <div className="flex items-center gap-2.5 px-2 pb-3.5 pt-1.5">
        <span
          aria-hidden="true"
          className="grid size-[26px] place-items-center rounded-lg bg-steel shadow-[inset_0_1.5px_0_rgba(255,255,255,.4),6px_6px_14px_rgba(69,123,157,.3),-4px_-4px_10px_rgba(255,255,255,.85)]"
        >
          <span className="size-[9px] rounded-[2px] bg-honeydew" />
        </span>
        <span className="text-[14.5px] font-bold tracking-tight text-ink">Content Suite</span>
      </div>

      <div className="clay clay-chip mb-2.5 flex items-center gap-2.5 px-2.5 py-2">
        <span
          aria-hidden="true"
          className="grid size-[22px] place-items-center rounded-[7px] bg-strawberry text-[10px] font-bold text-white shadow-[inset_0_1px_0_rgba(255,255,255,.35),3px_3px_8px_rgba(230,57,70,.35)]"
        >
          {workspaceName.charAt(0)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-semibold leading-tight text-ink">
            {workspaceName}
          </span>
          <span className="block text-[10.5px] text-ink-soft">Workspace</span>
        </span>
      </div>

      <nav aria-label="Principal" className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {grouped.map(({ group, items }) => (
          <div key={group}>
            <p className="px-2.5 pb-1 pt-3 text-[10.5px] font-bold uppercase tracking-[0.06em] text-ink-soft">
              {group === 'WORKSPACE'
                ? 'Workspace'
                : group === 'BRAND'
                  ? 'Brand'
                  : group === 'CREATE'
                    ? 'Create'
                    : group === 'SYSTEM'
                      ? 'System'
                      : 'Governance'}
            </p>
            <ul>
              {items.map((item) =>
                item.to ? (
                  <li key={item.id}>
                    <NavLink
                      to={item.to}
                      end
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-[13.5px] ${
                          isActive
                            ? 'clay nav-active font-semibold text-ink'
                            : 'font-medium text-ink-muted hover:bg-tint-steel'
                        }`
                      }
                    >
                      <span className="text-steel">
                        <NavIcon id={item.id} />
                      </span>
                      {item.label}
                    </NavLink>
                  </li>
                ) : (
                  <li key={item.id}>
                    <span
                      aria-disabled="true"
                      title="Se habilita en una change futura"
                      className="flex cursor-default items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-[13.5px] font-medium text-ink-muted opacity-45"
                    >
                      <span>
                        <NavIcon id={item.id} />
                      </span>
                      {item.label}
                      {/* Etiqueta explícita de future: no simula capacidad activa */}
                      <span className="ml-auto rounded-[5px] bg-tint-steel px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide">
                        Próximamente
                      </span>
                    </span>
                  </li>
                ),
              )}
            </ul>
          </div>
        ))}
      </nav>

      <div className="clay clay-inset mt-2 flex items-center gap-2.5 px-2.5 py-2">
        <span
          aria-hidden="true"
          className="grid size-7 place-items-center rounded-lg bg-frosted text-xs font-bold text-ink"
        >
          {profile?.displayName.charAt(0) ?? '?'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-semibold leading-tight text-ink">
            {profile?.displayName ?? 'Sin sesión'}
          </span>
          <span className="block truncate text-[10.5px] text-ink-soft">
            {role ? ROLE_LABELS[role] : '—'}
          </span>
        </span>
      </div>
      {/* Conmutador de identidad de dev: solo selecciona el token adjunto;
          el rol mostrado siempre proviene de la API. */}
      {nextDevRole && availableDevRoles.length > 1 && (
        <button
          type="button"
          onClick={() => switchRole(nextDevRole)}
          className="pt-1.5 text-center text-[10.5px] font-semibold text-ink-soft transition-colors hover:text-steel"
        >
          Cambiar a {DEMO_ROLE_LABELS[nextDevRole]} (dev)
        </button>
      )}
      <button
        type="button"
        onClick={() => void signOut()}
        className="pt-1.5 text-center text-[10.5px] font-semibold text-ink-soft transition-colors hover:text-strawberry"
      >
        Cerrar sesión
      </button>
    </div>
  )
}
