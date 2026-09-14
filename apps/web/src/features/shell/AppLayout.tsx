import { useCallback, useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router'
import { motion } from 'motion/react'
import { drawerContent } from '../../shared/motion'
import { CreateBrandPage } from '../session/CreateBrandPage'
import { useActiveBrand } from '../session/useActiveBrand'
import { SidebarContent } from './SidebarContent'

/** Duración de la salida animada del drawer (ms); después cierra el dialog. */
const DRAWER_EXIT_MS = 180

/**
 * Layout del shell: sidebar elevada en desktop, drawer en móvil.
 * El drawer usa <dialog> modal nativo: el foco entra y queda atrapado dentro,
 * el fondo es inerte para el teclado, Escape y clic en el backdrop cierran, y
 * el foco vuelve al botón que lo abrió. Solo el contenido interior se anima
 * (entrada horizontal breve); con prefers-reduced-motion el cierre es
 * inmediato y MotionConfig elimina el desplazamiento.
 */
export function AppLayout() {
  const brand = useActiveBrand()
  const [drawerPhase, setDrawerPhase] = useState<'open' | 'closing' | 'closed'>('closed')
  const dialogRef = useRef<HTMLDialogElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const closeTimerRef = useRef<number | null>(null)

  const finishClose = useCallback(() => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    dialogRef.current?.close()
  }, [])

  /**
   * Cierre controlado: anima la salida y luego cierra el dialog nativo.
   * Escape dispara el cancel nativo (cierre inmediato), lo que es correcto.
   */
  const requestClose = () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion || drawerPhase !== 'open') {
      finishClose()
      return
    }
    setDrawerPhase('closing')
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      dialogRef.current?.close()
    }, DRAWER_EXIT_MS)
  }

  // Al cruzar a desktop el drawer se cierra para no dejar un modal abierto.
  useEffect(() => {
    const query = window.matchMedia('(min-width: 1024px)')
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) finishClose()
    }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [finishClose])

  // Cancelar el timer de salida si el layout se desmonta a mitad de animación.
  useEffect(
    () => () => {
      if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current)
    },
    [],
  )

  // Identidad autenticada sin ninguna membresía: no hay marca que mostrar en
  // el shell -- se ofrece el onboarding self-serve en vez de un sidebar vacío.
  if (!brand) {
    return <CreateBrandPage />
  }

  return (
    <div className="flex min-h-screen w-full bg-canvas text-ink">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-steel"
      >
        Saltar al contenido
      </a>

      {/* Sidebar desktop: panel clay flotante sobre el lienzo (referencia) */}
      <aside className="sticky top-0 hidden h-screen w-[264px] shrink-0 p-4 pr-0 lg:block">
        <div className="clay-sidebar h-full min-h-0">
          <SidebarContent />
        </div>
      </aside>

      {/* Drawer móvil: dialog modal nativo; solo su interior se anima */}
      <dialog
        id="app-sidebar-drawer"
        ref={dialogRef}
        aria-label="Navegación principal"
        onClose={() => {
          if (closeTimerRef.current !== null) {
            window.clearTimeout(closeTimerRef.current)
            closeTimerRef.current = null
          }
          setDrawerPhase('closed')
          menuButtonRef.current?.focus()
        }}
        onClick={(event) => {
          // Clic sobre el backdrop: el target del evento es el propio dialog.
          if (event.target === dialogRef.current) requestClose()
        }}
        className="fixed inset-y-0 left-0 m-0 h-dvh max-h-dvh w-[276px] rounded-r-[26px] bg-sidebar p-0 shadow-[14px_0_36px_rgba(29,53,87,.22)] backdrop:bg-deep/30 backdrop:backdrop-blur-[2px] lg:hidden"
      >
        <motion.div
          initial={false}
          animate={drawerPhase}
          variants={drawerContent}
          className="h-full"
        >
          <SidebarContent onNavigate={requestClose} />
        </motion.div>
      </dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Barra superior móvil */}
        <header className="sticky top-0 z-30 flex items-center gap-3 bg-canvas/90 px-4 py-3 backdrop-blur-sm lg:hidden">
          <button
            type="button"
            ref={menuButtonRef}
            onClick={() => {
              setDrawerPhase('open')
              dialogRef.current?.showModal()
            }}
            aria-expanded={drawerPhase === 'open' || drawerPhase === 'closing'}
            aria-controls="app-sidebar-drawer"
            className="clay-icon clay-press size-10 text-steel"
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
          className="mx-auto w-full max-w-[1280px] flex-1 px-5 py-6 sm:px-8 lg:px-10 lg:py-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
