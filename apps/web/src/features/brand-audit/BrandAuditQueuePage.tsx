import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { EmptyState, ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { useActiveBrand } from '../session/useActiveBrand'
import { TYPE_VIEW } from '../creative/view'
import { useVisualQueue } from './api'
import { scoreBadge } from './view'

/**
 * Cola de Brand Audit (solo `VISUAL_REVIEWER`; la interfaz oculta el
 * control, la autoridad vive en el backend). Cada fila resume el ítem + su
 * visual vigente y el estado de la última auditoría, si existe.
 */
export function BrandAuditQueuePage() {
  const brand = useActiveBrand()
  const queue = useVisualQueue(brand?.role === 'VISUAL_REVIEWER')

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'VISUAL_REVIEWER') {
    return (
      <PermissionState
        title="Brand Audit es solo para Visual Compliance Reviewer"
        description="Tu rol no tiene esta superficie. La autoridad se resuelve en el backend."
      />
    )
  }
  if (queue.isPending) {
    return <LoadingState label="Cargando cola de auditoría visual…" />
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
        <p className="eyebrow">Brand Audit</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Visual Compliance</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          Visuales finales enviados por el Creator, listos para auditoría multimodal y decisión
          humana contra las reglas visuales del Brand DNA.
        </p>
      </motion.header>

      {queue.data.items.length === 0 ? (
        <EmptyState
          title="Nada pendiente de revisión visual"
          description="Cuando el Creator suba un visual sobre un ítem con contenido aprobado, aparecerá aquí."
        />
      ) : (
        <Card className="p-2">
          <ul>
            {queue.data.items.map((row) => (
              <li key={row.item.id}>
                <Link
                  to={`/brand-audit/${row.item.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-[9px] px-3 py-3 transition-colors hover:bg-tint-steel"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-semibold text-ink">{row.item.title}</p>
                    <p className="mt-0.5 text-[12px] text-ink-soft">
                      {TYPE_VIEW[row.item.type].label} · visual v{row.asset.version}
                    </p>
                  </div>
                  <div className="flex flex-none items-center gap-3">
                    {row.latest_audit ? (
                      <Badge variant={scoreBadge(row.latest_audit.score)} size="sm">
                        Score {row.latest_audit.score.toFixed(0)}/100
                      </Badge>
                    ) : (
                      <Badge variant="warning" size="sm">
                        Sin auditar
                      </Badge>
                    )}
                    <span className="text-[12px] font-semibold text-steel">Revisar visual →</span>
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
