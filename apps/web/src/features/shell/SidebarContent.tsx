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
  const { profile, switchRole, switchBrand, availableDevRoles, nextDevRole, signOut } =
    useSession()
  const role = profile?.activeMembership?.role
  const navItems = role ? NAV_ITEMS[role] : Object.values(NAV_ITEMS)[0]
  const grouped = groupNavItems(navItems)
  const workspaceName = profile?.activeMembership?.brand_name ?? WORKSPACE_FALLBACK_NAME
  const memberships = profile?.memberships ?? []

  return (
    <div className="flex h-full min-h-0 flex-col gap-1 p-4">
      <div className="flex items-center gap-3 px-1.5 pb-4 pt-1.5">
        <span
          aria-hidden="true"
          className="clay-icon size-9 bg-steel shadow-[6px_7px_14px_rgba(69,123,157,.35),-4px_-4px_10px_rgba(255,255,255,.9),inset_0_2px_0_rgba(255,255,255,.4),inset_-2px_-3px_6px_rgba(29,53,87,.3)]"
        >
          <span className="size-3 rounded-[4px] bg-honeydew shadow-[inset_0_-1px_2px_rgba(29,53,87,.25)]" />
        </span>
        <span className="text-[15px] font-bold tracking-tight text-ink">Content Suite</span>
      </div>

      <div className="clay clay-chip mb-3 flex items-center gap-3 px-3 py-2.5">
        <span
          aria-hidden="true"
          className="clay-icon size-8 shrink-0 bg-strawberry text-[12px] font-bold text-white shadow-[5px_6px_12px_rgba(230,57,70,.35),-3px_-3px_8px_rgba(255,255,255,.9),inset_0_1.5px_0_rgba(255,255,255,.4),inset_-2px_-3px_6px_rgba(29,53,87,.28)]"
        >
          {workspaceName.charAt(0)}
        </span>
        {memberships.length > 1 ? (
          <span className="min-w-0 flex-1">
            <label htmlFor="workspace-switcher" className="sr-only">
              Cambiar de workspace
            </label>
            <select
              id="workspace-switcher"
              value={profile?.activeMembership?.brand_id ?? ''}
              onChange={(event) => switchBrand(event.target.value)}
              className="w-full cursor-pointer truncate bg-transparent text-[13px] font-semibold leading-tight text-ink outline-none"
            >
              {memberships.map((membership) => (
                <option key={membership.brand_id} value={membership.brand_id}>
                  {membership.brand_name}
                </option>
              ))}
            </select>
            <span className="block text-[11px] text-ink-soft">
              Workspace · {memberships.length} marcas
            </span>
          </span>
        ) : (
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold leading-tight text-ink">
              {workspaceName}
            </span>
            <span className="block text-[11px] text-ink-soft">Workspace</span>
          </span>
        )}
      </div>

      <nav aria-label="Principal" className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {grouped.map(({ group, items }) => (
          <div key={group}>
            <p className="px-2.5 pb-1.5 pt-3.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-ink-soft">
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
            <ul className="flex flex-col gap-1">
              {items.map((item) =>
                item.to ? (
                  <li key={item.id}>
                    <NavLink
                      to={item.to}
                      end
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        `flex items-center gap-3 rounded-[14px] px-2.5 py-2 text-[13.5px] ${
                          isActive
                            ? 'clay nav-active font-semibold text-ink'
                            : 'nav-idle font-medium text-ink-muted'
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span
                            className={`grid size-8 shrink-0 place-items-center rounded-[10px] text-steel ${
                              isActive ? 'clay-icon' : ''
                            }`}
                          >
                            <NavIcon id={item.id} />
                          </span>
                          {item.label}
                        </>
                      )}
                    </NavLink>
                  </li>
                ) : (
                  <li key={item.id}>
                    <span
                      aria-disabled="true"
                      title="Se habilita en una change futura"
                      className="flex cursor-default items-center gap-3 rounded-[14px] px-2.5 py-2 text-[13.5px] font-medium text-ink-muted opacity-45"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-[10px]">
                        <NavIcon id={item.id} />
                      </span>
                      {item.label}
                      {/* Etiqueta explícita de future: no simula capacidad activa */}
                      <span className="ml-auto rounded-full bg-tint-steel px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide">
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

      <div className="clay clay-chip mt-2 flex items-center gap-3 px-3 py-2.5">
        <span
          aria-hidden="true"
          className="clay-icon size-8 shrink-0 bg-frosted text-[12px] font-bold text-ink"
        >
          {profile?.displayName.charAt(0) ?? '?'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold leading-tight text-ink">
            {profile?.displayName ?? 'Sin sesión'}
          </span>
          <span className="block truncate text-[11px] text-ink-soft">
            {role ? ROLE_LABELS[role] : '—'}
          </span>
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="shrink-0 text-ink-soft"
        >
          <path d="M9 6l6 6-6 6" />
        </svg>
      </div>
      {/* Conmutador de identidad de dev: solo selecciona el token adjunto;
          el rol mostrado siempre proviene de la API. */}
      {nextDevRole && availableDevRoles.length > 1 && (
        <button
          type="button"
          onClick={() => switchRole(nextDevRole)}
          className="rounded-[10px] pt-2 text-center text-[11px] font-semibold text-ink-soft transition-colors hover:text-steel"
        >
          Cambiar a {DEMO_ROLE_LABELS[nextDevRole]} (dev)
        </button>
      )}
      <button
        type="button"
        onClick={() => void signOut()}
        className="rounded-[10px] pt-1.5 text-center text-[11px] font-semibold text-ink-soft transition-colors hover:text-strawberry"
      >
        Cerrar sesión
      </button>
    </div>
  )
}
