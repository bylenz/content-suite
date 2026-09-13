import { Link } from 'react-router'
import { ErrorState } from '../../shared/components/StateViews'

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas p-6">
      <ErrorState
        title="Página no encontrada"
        description="La ruta que buscas no existe en esta entrega. Vuelve al dashboard del workspace."
      >
        <Link
          to="/"
          className="clay clay-cta px-5 py-2.5 text-sm font-semibold"
        >
          Volver al dashboard
        </Link>
      </ErrorState>
    </main>
  )
}
