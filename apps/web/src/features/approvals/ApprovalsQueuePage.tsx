import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { formatDate } from '../../shared/format'
import { EmptyState, ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { useActiveBrand } from '../session/useActiveBrand'
import { TYPE_VIEW } from '../creative/view'
import { useReviewQueue } from './api'

/**
 * Cola de Content Review (solo `CONTENT_REVIEWER`; la interfaz oculta el
 * control, la autoridad vive en el backend — mismo patrón que Creative
 * Studio y Brand DNA). Cada fila resume el ítem + la versión congelada que
 * espera decisión.
 */
export function ApprovalsQueuePage() {
  const brand = useActiveBrand()
  const queue = useReviewQueue(brand?.role === 'CONTENT_REVIEWER')

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'CONTENT_REVIEWER') {
    return (
      <PermissionState
        title="Approvals es solo para Content Reviewer"
        description="Tu rol no tiene esta superficie. La autoridad se resuelve en el backend."
      />
    )
  }
  if (queue.isPending) {
    return <LoadingState label="Cargando cola de revisión…" />
  }
  if (queue.isError) {
    const error = queue.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudo cargar la cola"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void queue.refetch()}
      />
    )
  }

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.header variants={surfaceItem}>
        <p className="eyebrow">Approvals</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Content Review</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          Contenido enviado por el Creator, en orden de llegada. La decisión aplica sobre la
          versión exacta congelada al enviar.
        </p>
      </motion.header>

      {queue.data.items.length === 0 ? (
        <EmptyState
          title="Nada pendiente de revisión"
          description="Cuando el Creator envíe contenido a revisión, aparecerá aquí en orden de llegada."
        />
      ) : (
        <Card className="p-2">
          <ul>
            {queue.data.items.map((row) => (
              <li key={row.item.id}>
                <Link
                  to={`/approvals/${row.item.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-[9px] px-3 py-3 transition-colors hover:bg-tint-steel"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-semibold text-ink">{row.item.title}</p>
                    <p className="mt-0.5 text-[12px] text-ink-soft">
                      {TYPE_VIEW[row.item.type].label} · v{row.submitted_version.version} · enviado{' '}
                      {formatDate(row.submitted_at)}
                    </p>
                  </div>
                  <div className="flex flex-none items-center gap-3">
                    <Badge variant="warning" size="sm">
                      En cola
                    </Badge>
                    <span className="text-[12px] font-semibold text-steel">Revisar →</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </motion.div>
  )
}
