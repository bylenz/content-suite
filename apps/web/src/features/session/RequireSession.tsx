import { Outlet } from 'react-router'
import { useSession } from './useSession'
import { LoadingState, SessionMissingState } from '../../shared/components/StateViews'

/**
 * Ruta protegida del shell: solo decide si hay sesión para renderizar.
 * No valida permisos; eso es autoridad del backend.
 */
export function RequireSession() {
  const { status, enterDemoSession } = useSession()

  if (status === 'initializing') {
    return <LoadingState label="Estableciendo sesión…" />
  }

  if (status === 'anonymous') {
    return <SessionMissingState onEnterDemo={() => enterDemoSession()} />
  }

  return <Outlet />
}
