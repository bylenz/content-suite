import { Link, useParams } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import { Badge } from '@/components/ui/badge'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { useActiveBrand, } from '../session/useActiveBrand'
import { useBrandDnaVersion } from './api'
import { DocumentSectionView } from './DocumentSectionView'
import { SECTIONS, sectionTitle } from './sections'
import { formatDate, KNOWLEDGE_STATUS_VIEW, VERSION_STATUS_VIEW } from './statusView'

/**
 * Detalle de una versión publicada (documento íntegro e inmutable). Un
 * revisor que solicite una versión en DRAFT recibe 404 del backend: la vista
 * no distingue ese caso de una versión inexistente.
 */
export function BrandDnaVersionPage() {
  const params = useParams<{ version: string }>()
  const brand = useActiveBrand()
  const versionNumber = Number.parseInt(params.version ?? '', 10)

  const query = useBrandDnaVersion(brand?.brandId ?? '', versionNumber)

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (Number.isNaN(versionNumber)) {
    return (
      <ErrorState
        title="Versión inválida"
        description="El número de versión solicitado no es válido."
      >
        <Link to="/brand-dna" className="text-[13px] font-semibold text-steel">
          ← Volver a Brand DNA
        </Link>
      </ErrorState>
    )
  }
  if (query.isPending) {
    return <LoadingState label="Cargando versión…" />
  }
  if (query.isError) {
    const error = query.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="Versión no encontrada"
        description={
          error instanceof Error
            ? error.message
            : 'La versión no existe o no es visible para tu rol.'
        }
        onRetry={() => void query.refetch()}
      >
        <Link to="/brand-dna" className="text-[13px] font-semibold text-steel">
          ← Volver a Brand DNA
        </Link>
      </ErrorState>
    )
  }

  const version = query.data
  const status = VERSION_STATUS_VIEW[version.status]
  const knowledge = KNOWLEDGE_STATUS_VIEW[version.knowledge_status]

  return (
    <motion.div
      variants={surfaceGroup}
      initial="hidden"
      animate="show"
      className="flex flex-col gap-5"
    >
      <motion.div variants={surfaceItem}>
        <Link
          to="/brand-dna"
          className="text-[12.5px] font-semibold text-ink-soft hover:text-steel"
        >
          ← Brand DNA
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            Versión {version.version}
          </h1>
          <Badge variant={status.badge}>{status.label}</Badge>
          <Badge variant={knowledge.badge}>Knowledge: {knowledge.label}</Badge>
        </div>
        <p className="mt-1.5 text-[12.5px] text-ink-soft">
          Creada {formatDate(version.created_at)} · Publicada {formatDate(version.published_at)}
        </p>
      </motion.div>

      <div className="flex flex-col gap-4">
        {SECTIONS.map((section) => (
          <motion.div key={section.key} variants={surfaceItem} className="flex flex-col gap-3">
            <h2 className="text-[15px] font-bold text-ink">{sectionTitle(section.key)}</h2>
            <DocumentSectionView section={section.key} document={version.document} />
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}
