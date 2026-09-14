import { DropdownMenu } from 'radix-ui'
import type { Membership } from '../../shared/api/types'
import { ROLE_LABELS } from '../session/roles'

const CHEVRON = (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.4"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    className="shrink-0 text-ink-soft transition-transform duration-200 group-data-[state=open]:rotate-180"
  >
    <path d="M6 9l6 6 6-6" />
  </svg>
)

/** Avatar clay con la inicial de la marca (mismo chip que usa el sidebar). */
export function BrandAvatar({ name, size = 'md' }: { name: string; size?: 'sm' | 'md' }) {
  return (
    <span
      aria-hidden="true"
      className={`clay-icon shrink-0 bg-strawberry font-bold text-white shadow-[5px_6px_12px_rgba(230,57,70,.35),-3px_-3px_8px_rgba(255,255,255,.9),inset_0_1.5px_0_rgba(255,255,255,.4),inset_-2px_-3px_6px_rgba(29,53,87,.28)] ${
        size === 'sm' ? 'size-7 text-[11px]' : 'size-8 text-[12px]'
      }`}
    >
      {name.charAt(0)}
    </span>
  )
}

/**
 * Conmutador de workspace (solo con dos o más membresías): el chip clay del
 * sidebar es el disparador y despliega un panel clay con todas las marcas de
 * la identidad, su rol en cada una y la activa marcada. Radix aporta teclado,
 * foco y cierre por Escape/clic fuera; la selección llama a `switchBrand`,
 * que persiste la elección y limpia las queries de marca.
 */
export function WorkspaceSwitcher({
  memberships,
  active,
  onSwitch,
}: {
  memberships: Membership[]
  active: Membership
  onSwitch: (brandId: string) => void
}) {
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Cambiar de workspace"
          className="clay clay-chip clay-press group mb-1.5 flex w-full items-center gap-3 px-3 py-2.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-steel/40"
        >
          <BrandAvatar name={active.brand_name} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold leading-tight text-ink">
              {active.brand_name}
            </span>
            <span className="block text-[11px] text-ink-soft">
              Workspace · {memberships.length} marcas
            </span>
          </span>
          {CHEVRON}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={8}
          collisionPadding={12}
          className="clay-menu z-50 w-[var(--radix-dropdown-menu-trigger-width)] min-w-[228px] p-2 outline-none"
        >
          <DropdownMenu.Label className="px-2.5 pb-1.5 pt-1 text-[10.5px] font-bold uppercase tracking-[0.08em] text-ink-soft">
            Tus workspaces
          </DropdownMenu.Label>
          <DropdownMenu.RadioGroup
            value={active.brand_id}
            onValueChange={(brandId) => {
              if (brandId !== active.brand_id) onSwitch(brandId)
            }}
            className="flex flex-col gap-1"
          >
            {memberships.map((membership) => (
              <DropdownMenu.RadioItem
                key={membership.brand_id}
                value={membership.brand_id}
                textValue={membership.brand_name}
                className="clay-menu-item flex cursor-pointer select-none items-center gap-3 rounded-[12px] px-2.5 py-2 outline-none"
              >
                <BrandAvatar name={membership.brand_name} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold leading-tight text-ink">
                    {membership.brand_name}
                  </span>
                  <span className="block text-[11px] text-ink-soft">
                    {ROLE_LABELS[membership.role]}
                  </span>
                </span>
                <DropdownMenu.ItemIndicator className="clay-dot grid size-5 shrink-0 place-items-center bg-success-solid text-white">
                  <svg
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M5 12l5 5L20 7" />
                  </svg>
                </DropdownMenu.ItemIndicator>
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
