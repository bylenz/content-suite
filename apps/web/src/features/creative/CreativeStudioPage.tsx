import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { formatDate } from '../../shared/format'
import { EmptyState, ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useActiveBrand } from '../session/useActiveBrand'
import { useCreativeItems } from './api'
import { TYPE_VIEW, WORKFLOW_STATUS_VIEW } from './view'
import type { CreativeItemType, ItemSummary } from './types'

const TYPE_ORDER: CreativeItemType[] = ['PRODUCT_DESCRIPTION', 'VIDEO_SCRIPT', 'IMAGE_PROMPT']

/**
 * Creative Studio (home): tipos de contenido disponibles + listado real de
 * ítems de la marca activa con su estado de workflow y versión vigente
 * (starter-design: tarjetas de tipo y Recent Creations). Los revisores ven
 * lectura; la autoridad de escritura vive en el backend.
 */
export function CreativeStudioPage() {
  const brand = useActiveBrand()
  const items = useCreativeItems(brand?.brandId ?? '')

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }

  if (items.isPending) {
    return <LoadingState label="Cargando Creative Studio…" />
  }
  if (items.isError) {
    const error = items.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudo cargar el contenido"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void items.refetch()}
      />
    )
  }

  const isCreator = brand.role === 'CREATOR'

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.header variants={surfaceItem}>
        <p className="eyebrow">Creative Studio</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">
          Contenido consistente con {brand.brandName}
        </h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          Crea descripciones, guiones y prompts que heredan el tono y las reglas del Brand DNA.
        </p>
      </motion.header>

      {isCreator && (
        <motion.div variants={surfaceItem} className="flex flex-wrap gap-4">
          {TYPE_ORDER.map((type) => (
            <Link
              key={type}
              to={`/creative/new?type=${type}`}
              className="clay clay-card min-w-[220px] flex-1 px-5 py-4 transition-colors hover:bg-tint-frosted"
            >
              <p className="text-[14.5px] font-bold text-ink">{TYPE_VIEW[type].label}</p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-muted">
                {TYPE_VIEW[type].description}
              </p>
              <p className="mt-3 text-[12.5px] font-semibold text-steel">Crear →</p>
            </Link>
          ))}
        </motion.div>
      )}

      <motion.section variants={surfaceItem} aria-label="Creaciones de la marca">
        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.06em] text-ink-soft">
          Contenido de la marca
        </p>
        {items.data.items.length === 0 ? (
          <EmptyState
            title="Aún no hay contenido"
            description={
              isCreator
                ? 'Crea tu primer ítem desde las tarjetas de arriba: el brief alimenta la generación con Brand Knowledge.'
                : 'Cuando el Creator cree contenido de esta marca, aparecerá aquí en modo lectura.'
            }
          >
            {isCreator && (
              <Button asChild>
                <Link to="/creative/new?type=PRODUCT_DESCRIPTION">Crear Product Description</Link>
              </Button>
            )}
          </EmptyState>
        ) : (
          <Card className="p-2">
            <ul>
              {items.data.items.map((item) => (
                <ItemRow key={item.id} item={item} />
              ))}
            </ul>
          </Card>
        )}
      </motion.section>
    </motion.div>
  )
}

function ItemRow({ item }: { item: ItemSummary }) {
  const status = WORKFLOW_STATUS_VIEW[item.workflow_status]
  const type = TYPE_VIEW[item.type]
  return (
    <li>
      <Link
        to={`/creative/items/${item.id}`}
        className="flex flex-wrap items-center justify-between gap-3 rounded-[9px] px-3 py-3 transition-colors hover:bg-tint-steel"
      >
        <div className="min-w-0">
          <p className="truncate text-[13.5px] font-semibold text-ink">{item.title}</p>
          <p className="mt-0.5 text-[12px] text-ink-soft">
            {type.label} · v{item.latest_version} · {formatDate(item.updated_at)}
          </p>
        </div>
        <div className="flex flex-none items-center gap-3">
          <Badge variant={status.badge} size="sm">
            {status.label}
          </Badge>
          <span className="text-[12px] font-semibold text-steel">Abrir →</span>
        </div>
      </Link>
    </li>
  )
}
