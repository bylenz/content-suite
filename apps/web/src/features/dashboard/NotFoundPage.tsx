import { Link } from 'react-router'
import { ErrorState } from '../../shared/components/StateViews'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas p-6">
      <ErrorState
        title="Página no encontrada"
        description="La ruta que buscas no existe en esta entrega. Vuelve al dashboard del workspace."
      >
        <Button asChild>
          <Link to="/">Volver al dashboard</Link>
        </Button>
      </ErrorState>
    </main>
  )
}
