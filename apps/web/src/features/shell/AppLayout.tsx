import { useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router'
import { SidebarContent } from './SidebarContent'

/**
 * Layout del shell: sidebar elevada en desktop, drawer en móvil.
 * El drawer usa <dialog> modal nativo: el foco entra y queda atrapado dentro,
 * el fondo es inerte para el teclado, Escape y clic en el backdrop cierran, y
 * el foco vuelve al botón que lo abrió.
 */
export function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  const closeMobileNav = () => dialogRef.current?.close()

  // Al cruzar a desktop el drawer se cierra para no dejar un modal abierto.
  useEffect(() => {
    const query = window.matchMedia('(min-width: 1024px)')
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) closeMobileNav()
    }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return (
    <div className="flex min-h-screen w-full bg-canvas text-ink">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-steel"
      >
        Saltar al contenido
      </a>

      {/* Sidebar desktop */}
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 border-r border-line bg-white/95 lg:block">
        <SidebarContent />
      </aside>

      {/* Drawer móvil: dialog modal nativo */}
      <dialog
        id="app-sidebar-drawer"
        ref={dialogRef}
        aria-label="Navegación principal"
        onClose={() => {
          setMobileNavOpen(false)
          menuButtonRef.current?.focus()
        }}
        onClick={(event) => {
          // Clic sobre el backdrop: el target del evento es el propio dialog.
          if (event.target === dialogRef.current) closeMobileNav()
        }}
        className="fixed inset-y-0 left-0 m-0 h-dvh max-h-dvh w-[268px] bg-white p-0 shadow-[10px_0_28px_rgba(29,53,87,.18)] backdrop:bg-deep/30 backdrop:backdrop-blur-[2px] lg:hidden"
      >
        <SidebarContent onNavigate={closeMobileNav} />
      </dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Barra superior móvil */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white/95 px-4 py-3 lg:hidden">
          <button
            type="button"
            ref={menuButtonRef}
            onClick={() => {
              setMobileNavOpen(true)
              dialogRef.current?.showModal()
            }}
            aria-expanded={mobileNavOpen}
            aria-controls="app-sidebar-drawer"
            className="clay clay-chip grid size-9 place-items-center text-steel"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
            <span className="sr-only">Abrir navegación</span>
          </button>
          <span className="text-[14.5px] font-bold tracking-tight text-ink">Content Suite</span>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-[1240px] flex-1 px-5 py-8 sm:px-8 lg:px-12 lg:py-10"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
