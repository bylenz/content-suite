import { Outlet } from 'react-router'
import { useSession } from './useSession'
import type { DemoRole } from './roles'
import { LoadingState, SessionMissingState } from '../../shared/components/StateViews'

/**
 * Ruta protegida del shell: solo decide si hay sesión para renderizar.
 * No valida permisos; eso es autoridad del backend.
 */
export function RequireSession() {
  const { status, authenticate, availableDevRoles, authError, signInWithMagicLink } = useSession()

  if (status === 'initializing') {
    return <LoadingState label="Estableciendo sesión…" />
  }

  if (status === 'anonymous') {
    return (
      <SessionMissingState
        // Solo en desarrollo existe el mapping ignorado de tokens de dev.
        devRoles={availableDevRoles}
        authError={authError}
        onEnterDemo={
          availableDevRoles.length > 0 ? (role: DemoRole) => authenticate(role) : undefined
        }
        onSignInWithMagicLink={signInWithMagicLink}
      />
    )
  }

  return <Outlet />
}
