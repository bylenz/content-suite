import { useState } from 'react'
import { Link } from 'react-router'
import { AnimatePresence, motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/client'
import type { BrandDnaVersionSummary } from '../../shared/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { crossfadeTransition, feedbackItem, surfaceGroup, surfaceItem } from '../../shared/motion'
import { EmptyState, ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { useActiveBrand } from '../session/useActiveBrand'
import { useBrandDna, useBrandDnaVersions, usePublishDraft, useSyncKnowledge } from './api'
import { BrandAssetsPanel } from './BrandAssetsPanel'
import { DocumentSectionView } from './DocumentSectionView'
import { SECTIONS } from './sections'
import { formatDate, KNOWLEDGE_STATUS_VIEW, VERSION_STATUS_VIEW } from './statusView'

type Panel =
  | 'overview'
  | 'identity'
  | 'voice'
  | 'communication'
  | 'visual_rules'
  | 'restrictions'
  | 'assets'
  | 'versions'

const PANEL_ITEMS: { id: Panel; label: string }[] = [
  { id: 'overview', label: 'Resumen' },
  ...SECTIONS.map((section) => ({ id: section.key as Panel, label: section.label })),
  { id: 'assets', label: 'Brand Assets' },
  { id: 'versions', label: 'Versiones' },
]

function VersionRow({ version }: { version: BrandDnaVersionSummary }) {
  const status = VERSION_STATUS_VIEW[version.status]
  const knowledge = KNOWLEDGE_STATUS_VIEW[version.knowledge_status]
  return (
    <motion.li variants={surfaceItem}>
      <Link
        to={`/brand-dna/versions/${version.version}`}
        className="clay clay-subtle clay-hover-raise flex flex-wrap items-center justify-between gap-3 px-4.5 py-3.5"
      >
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
            Versión {version.version}
            <Badge variant={status.badge} size="sm">
              {status.label}
            </Badge>
          </p>
          <p className="mt-1 text-[11.5px] text-ink-soft">
            Publicada {formatDate(version.published_at)} · Creada {formatDate(version.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={knowledge.badge} size="sm">{knowledge.label}</Badge>
          <span className="text-[12px] font-semibold text-steel">Ver documento →</span>
        </div>
      </Link>
    </motion.li>
  )
}

/**
 * Superficie Brand DNA: navegación de secciones (Resumen + cinco secciones +
 * Versiones), vista editorial del documento, edición del borrador y
 * publicación con `expected_draft_id` (manejo del 409). El Creator además
 * dispara la sincronización explícita de Knowledge sobre la versión ACTIVE
 * (deshabilitada en OUTDATED con ese motivo). Los revisores ven solo el DNA
 * publicado, sin controles de escritura ni datos de borrador.
 * El cambio de sección es un crossfade breve de opacidad (sin mover el texto
 * editorial); las filas de versión entran escalonadas y el feedback de
 * publicación/sync (éxito/error) aparece con opacidad + desplazamiento mínimo.
 */
export function BrandDnaPage() {
  const brand = useActiveBrand()
  const [panel, setPanel] = useState<Panel>('overview')
  const [publishError, setPublishError] = useState<string | null>(null)
  const [publishSuccess, setPublishSuccess] = useState<string | null>(null)

  const overview = useBrandDna(brand?.brandId ?? '')
  const versions = useBrandDnaVersions(brand?.brandId ?? '')
  const publish = usePublishDraft(brand?.brandId ?? '')
  const syncKnowledge = useSyncKnowledge(brand?.brandId ?? '')
  const queryClient = useQueryClient()
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncSuccess, setSyncSuccess] = useState<string | null>(null)

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  const isCreator = brand.role === 'CREATOR'

  if (overview.isPending) {
    return <LoadingState label="Cargando Brand DNA…" />
  }
  if (overview.isError) {
    const error = overview.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudo cargar el Brand DNA"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void overview.refetch()}
      />
    )
  }

  const { active, draft } = overview.data
  // El Creator trabaja sobre su borrador cuando existe; los revisores solo ven
  // la versión publicada (el backend ya entrega draft: null a revisores).
  const displayed = (isCreator && draft) || active
  const hasAnyVersion = active !== null || draft !== null || (versions.data?.versions.length ?? 0) > 0

  if (!hasAnyVersion && panel === 'overview') {
    return (
      <motion.div
        variants={surfaceGroup}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <motion.header variants={surfaceItem}>
          <p className="eyebrow">Brand DNA</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">
            La fuente de verdad de {brand.brandName}
          </h1>
        </motion.header>
        <motion.div variants={surfaceItem}>
          <EmptyState
            title="Aún no existe un Brand DNA"
            description={
              isCreator
                ? 'Define cómo comunica, se comporta y se presenta tu marca. Content Suite usará estas reglas en cada generación y auditoría.'
                : 'Esta marca todavía no ha publicado su Brand DNA. Cuando el Creator lo publique, lo verás aquí en modo lectura.'
            }
          >
            {isCreator && (
              <div className="flex flex-wrap justify-center gap-2.5">
                <Button asChild>
                  <Link to="/brand-dna/generate">Generar con IA</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/brand-dna/create">Crear manualmente</Link>
                </Button>
              </div>
            )}
          </EmptyState>
        </motion.div>
      </motion.div>
    )
  }

  const activeKnowledge = active ? KNOWLEDGE_STATUS_VIEW[active.knowledge_status] : null

  async function onPublish(expectedDraftId: string) {
    setPublishError(null)
    setPublishSuccess(null)
    try {
      const published = await publish.mutateAsync(expectedDraftId)
      setPublishSuccess(`Publicación completada: v${published.version} es la versión activa.`)
    } catch (error) {
      if (error instanceof ApiError && error.code === 'INVALID_WORKFLOW_TRANSITION') {
        setPublishError(
          'La publicación entró en conflicto con el estado actual (p. ej. otra publicación concurrente o un borrador desactualizado). Se recargó el estado real.',
        )
        // La mutación ya invalidó las queries; refetch inmediato para mostrar
        // el estado vigente.
        void queryClient.invalidateQueries({ queryKey: ['brand-dna', brand?.brandId] })
      } else {
        setPublishError(error instanceof Error ? error.message : 'Error al publicar.')
      }
    }
  }

  async function onSyncKnowledge() {
    setSyncError(null)
    setSyncSuccess(null)
    try {
      const result = await syncKnowledge.mutateAsync()
      setSyncSuccess(
        `Knowledge sincronizado: ${result.chunk_count} reglas indexadas (v${result.version}).`,
      )
    } catch (error) {
      // El envelope ya trae el mensaje sanitizado (403/404/409/503).
      setSyncError(error instanceof Error ? error.message : 'Error al sincronizar Knowledge.')
      void queryClient.invalidateQueries({ queryKey: ['brand-dna', brand?.brandId] })
    }
  }

  return (
    <motion.div
      variants={surfaceGroup}
      initial="hidden"
      animate="show"
      className="flex flex-col gap-6"
    >
      <motion.header variants={surfaceItem} className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Brand DNA</p>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-ink">{brand.brandName}</h1>
            {draft ? (
              <Badge variant="info">Borrador · v{draft.version}</Badge>
            ) : active ? (
              <Badge variant="success">Activa · v{active.version}</Badge>
            ) : (
              <Badge variant="neutral">Sin publicar</Badge>
            )}
          </div>
        </div>
        {/* Controles de escritura: solo Creator (la autoridad real es el backend) */}
        {isCreator && draft && (
          <div className="flex gap-2.5">
            <Button
              asChild
              variant="outline"
              className="px-4 text-[13px] text-steel"
            >
              <Link to="/brand-dna/edit">Editar borrador</Link>
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => void onPublish(draft.id)}
              disabled={publish.isPending}
            >
              {publish.isPending ? 'Publicando…' : `Publicar v${draft.version}`}
            </Button>
          </div>
        )}
        {isCreator && !draft && active && (
          <Button asChild size="sm">
            <Link to="/brand-dna/edit">Editar documento</Link>
          </Button>
        )}
      </motion.header>

      {/* Feedback de publicación/sync: éxito/error con opacidad + desplazamiento mínimo */}
      <AnimatePresence>
        {publishSuccess && (
          <motion.p
            key="publish-success"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="status"
            className="clay clay-tile bg-success-bg px-4 py-3 text-[13px] font-medium text-success-fg"
          >
            {publishSuccess}
          </motion.p>
        )}
        {publishError && (
          <motion.p
            key="publish-error"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="alert"
            className="clay clay-tile bg-warning-bg px-4 py-3 text-[13px] font-medium text-warning-fg"
          >
            {publishError}
          </motion.p>
        )}
        {syncSuccess && (
          <motion.p
            key="sync-success"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="status"
            className="clay clay-tile bg-success-bg px-4 py-3 text-[13px] font-medium text-success-fg"
          >
            {syncSuccess}
          </motion.p>
        )}
        {syncError && (
          <motion.p
            key="sync-error"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="alert"
            className="clay clay-tile bg-danger-bg px-4 py-3 text-[13px] font-medium text-danger-fg"
          >
            {syncError}
          </motion.p>
        )}
      </AnimatePresence>

      {activeKnowledge && active && (
        <motion.div
          variants={surfaceItem}
          className={`clay-tile flex flex-wrap items-center justify-between gap-3 px-4 py-3 ${activeKnowledge.banner}`}
          role="status"
        >
          <p className="min-w-0 text-[13px] font-medium">
            Estado de Knowledge: {activeKnowledge.label}.
            {active.knowledge_status === 'NOT_SYNCED' &&
              ' Sincroniza para que generación y auditoría usen esta versión.'}
            {active.knowledge_status === 'SYNCING' && ' La sincronización está en curso.'}
            {active.knowledge_status === 'FAILED' && ' Puedes reintentar la sincronización.'}
            {active.knowledge_status === 'OUTDATED' &&
              ' Hay un borrador con cambios pendientes: publícalo para volver a sincronizar.'}
          </p>
          {isCreator &&
            (active.knowledge_status === 'OUTDATED' ? (
              <span className="text-[12px] font-medium opacity-80">
                Sync deshabilitado: publica primero el borrador
              </span>
            ) : (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="px-3.5 text-current"
                onClick={() => void onSyncKnowledge()}
                disabled={syncKnowledge.isPending || active.knowledge_status === 'SYNCING'}
              >
                {syncKnowledge.isPending || active.knowledge_status === 'SYNCING'
                  ? 'Sincronizando…'
                  : 'Sincronizar Knowledge'}
              </Button>
            ))}
        </motion.div>
      )}

      {isCreator && draft && active && (
        <motion.p
          variants={surfaceItem}
          className="clay-tile bg-tint-frosted px-4 py-3 text-[13px] text-ink-muted"
          role="status"
        >
          Estás viendo tu borrador v{draft.version}. La versión activa publicada (v{active.version})
          permanece inmutable hasta que publiques.
        </motion.p>
      )}

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Navegación de secciones (sin animación: navegación de alta frecuencia) */}
        <nav
          aria-label="Secciones del Brand DNA"
          className="flex gap-1.5 overflow-x-auto pb-1 lg:w-[180px] lg:flex-none lg:flex-col lg:overflow-visible lg:pb-0 lg:pt-1.5"
        >
          {PANEL_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setPanel(item.id)}
              aria-current={panel === item.id}
              className={`whitespace-nowrap rounded-[12px] px-3 py-2 text-left text-[13.5px] ${
                panel === item.id
                  ? 'clay nav-active font-semibold text-ink'
                  : 'nav-idle font-medium text-ink-muted'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0 flex-1 lg:max-w-[740px]">
          {/* Crossfade breve de opacidad entre secciones; el texto estable
              no se anima durante la lectura. */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={panel}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={crossfadeTransition}
            >
              {panel === 'overview' && displayed && (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                    {SECTIONS.map((section) => (
                      <div
                        key={section.key}
                        className="clay clay-tile clay-hover-raise bg-tint-frosted px-3.5 py-3"
                      >
                        <p className="text-[22px] font-extrabold leading-none text-ink">
                          {displayed.section_counts[section.key] ?? 0}
                        </p>
                        <p className="mt-1 text-[11px] text-ink-soft">{section.label}</p>
                      </div>
                    ))}
                  </div>
                  {SECTIONS.map((section) => (
                    <DocumentSectionView key={section.key} section={section.key} document={displayed.document} />
                  ))}
                </div>
              )}

              {panel !== 'overview' && panel !== 'assets' && panel !== 'versions' && displayed && (
                <DocumentSectionView section={panel} document={displayed.document} />
              )}

              {panel === 'assets' && (
                <BrandAssetsPanel brandId={brand.brandId} isCreator={isCreator} />
              )}

              {panel === 'versions' && (
                <div className="flex flex-col gap-4">
                  <h2 className="text-[15px] font-bold text-ink">Historial de versiones</h2>
                  {versions.isPending && <LoadingState label="Cargando versiones…" />}
                  {versions.isError && (
                    <ErrorState
                      title="No se pudo cargar el historial"
                      description={
                        versions.error instanceof Error
                          ? versions.error.message
                          : 'Error desconocido de la API.'
                      }
                      onRetry={() => void versions.refetch()}
                    />
                  )}
                  {versions.data && versions.data.versions.length === 0 && (
                    <EmptyState
                      title="Sin versiones publicadas"
                      description={
                        isCreator
                          ? 'Publica tu primer borrador para iniciar el historial.'
                          : 'Cuando el Creator publique la primera versión, aparecerá aquí.'
                      }
                    />
                  )}
                  {versions.data && versions.data.versions.length > 0 && (
                    <motion.ul
                      variants={surfaceGroup}
                      initial="hidden"
                      animate="show"
                      className="flex flex-col gap-2.5"
                    >
                      {versions.data.versions.map((version) => (
                        <VersionRow key={version.id} version={version} />
                      ))}
                    </motion.ul>
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}
