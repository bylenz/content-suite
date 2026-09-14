import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { AnimatePresence, motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import { formatDate } from '../../shared/format'
import { surfaceGroup, surfaceItem, feedbackItem } from '../../shared/motion'
import { EmptyState, ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useActiveBrand } from '../session/useActiveBrand'
import { ORIGIN_VIEW, TYPE_VIEW, WORKFLOW_STATUS_VIEW } from '../creative/view'
import { VersionOutputView } from '../creative/VersionOutputView'
import { useApprove, useRequestChanges, useReviewDetail, useReviewHistory } from './api'
import { RequestChangesForm } from './RequestChangesForm'
import { describeReviewError } from './view'
import type { WorkflowEventOut } from './types'

const EVENT_LABELS: Record<string, string> = {
  SUBMITTED: 'Enviado a revisión',
  CONTENT_APPROVED: 'Contenido aprobado',
  CONTENT_CHANGES_REQUESTED: 'Cambios solicitados',
  VISUAL_UPLOADED: 'Visual subido',
  VISUAL_CHANGES_REQUESTED: 'Cambios visuales solicitados',
  FINAL_APPROVED: 'Aprobado final',
}

/**
 * Detalle de Content Review: versión congelada exacta (misma superficie
 * editorial densa que Creative Studio, sin controles de edición), contexto
 * aplicado, decisión previa si existe y acciones approve/request-changes.
 * Idempotente por diseño del backend: un reintento nunca duplica la decisión.
 */
export function ApprovalDetailPage() {
  const { itemId = '' } = useParams()
  const brand = useActiveBrand()
  const detail = useReviewDetail(itemId)
  const history = useReviewHistory(itemId)
  const approve = useApprove(itemId)
  const requestChanges = useRequestChanges(itemId)

  const [requestingChanges, setRequestingChanges] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

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
  if (detail.isPending) {
    return <LoadingState label="Cargando revisión…" />
  }
  if (detail.isError) {
    const error = detail.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudo cargar la revisión"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void detail.refetch()}
      />
    )
  }

  const data = detail.data
  const version = data.submitted_version
  const pending = data.item.workflow_status === 'PENDING_CONTENT_REVIEW'
  const anyPending = approve.isPending || requestChanges.isPending

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null)
    try {
      await action()
    } catch (error) {
      setActionError(describeReviewError(error))
    }
  }

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.header variants={surfaceItem}>
        <Link to="/approvals" className="text-[12.5px] font-semibold text-ink-soft hover:text-steel">
          ← Cola de revisión
        </Link>
        <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-ink">{data.item.title}</h1>
          <Badge variant={pending ? 'warning' : WORKFLOW_STATUS_VIEW[data.item.workflow_status].badge}>
            {pending ? 'Pendiente de decisión' : WORKFLOW_STATUS_VIEW[data.item.workflow_status].label}
          </Badge>
        </div>
        <p className="mt-1 text-[12.5px] text-ink-soft">{TYPE_VIEW[data.item.type].label}</p>
      </motion.header>

      <AnimatePresence>
        {actionError && (
          <motion.p
            key="action-error"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="alert"
            className="clay clay-subtle bg-danger-bg px-4 py-3 text-[13px] font-medium text-danger-fg"
          >
            {actionError}
          </motion.p>
        )}
      </AnimatePresence>

      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="min-w-0 flex-1 lg:max-w-[740px]">
          {!version ? (
            <EmptyState
              title="Nada enviado todavía"
              description="Este ítem aún no tiene una versión congelada esperando decisión."
            />
          ) : (
            <Card className="px-5 py-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <p className="text-[13.5px] font-bold text-ink">
                  v{version.version} · {ORIGIN_VIEW[version.origin].label}
                </p>
                {version.consistency_score !== null && (
                  <Badge variant={version.consistency_score >= 80 ? 'success' : 'warning'} size="sm">
                    Score {version.consistency_score.toFixed(0)}/100
                  </Badge>
                )}
              </div>
              {version.output ? (
                <VersionOutputView output={version.output} />
              ) : (
                <p className="text-[13px] leading-relaxed text-ink-soft">Versión sin contenido.</p>
              )}

              {data.latest_review && (
                <div className="clay clay-subtle mt-4 px-4 py-3.5">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-ink-soft">
                    Última decisión
                  </p>
                  <p className="mt-1.5 text-[13px] font-semibold text-ink">
                    {data.latest_review.decision === 'APPROVED' ? 'Aprobado' : 'Cambios solicitados'}
                  </p>
                  {data.latest_review.feedback && (
                    <p className="mt-1 text-[12.5px] leading-relaxed text-ink-muted">
                      {data.latest_review.feedback}
                    </p>
                  )}
                </div>
              )}

              {pending && (
                <div className="mt-5 border-t border-line pt-4">
                  {requestingChanges ? (
                    <RequestChangesForm
                      submitting={requestChanges.isPending}
                      serverError={null}
                      onSubmit={(feedback) =>
                        void runAction(async () => {
                          await requestChanges.mutateAsync(feedback)
                          setRequestingChanges(false)
                        })
                      }
                      onCancel={() => setRequestingChanges(false)}
                    />
                  ) : (
                    <div className="flex flex-wrap gap-2.5">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void runAction(() => approve.mutateAsync())}
                        disabled={anyPending}
                      >
                        {approve.isPending ? 'Aprobando…' : `Aprobar v${version.version}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setRequestingChanges(true)}
                        disabled={anyPending}
                      >
                        Solicitar cambios
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>

        <aside className="flex w-full flex-col gap-4 lg:w-[300px] lg:flex-none">
          {data.applied_context && (
            <Card className="px-4 py-4">
              <p className="text-[13px] font-bold text-ink">Contexto aplicado</p>
              <div className="mt-2.5 flex flex-col gap-2 text-[12.5px] text-ink-muted">
                <p>
                  <span className="text-ink-soft">Reglas aplicadas: </span>
                  {data.applied_context.applied_rule_ids.length > 0
                    ? `${data.applied_context.applied_rule_ids.length} reglas recuperadas`
                    : 'ninguna citada (edición humana)'}
                </p>
              </div>
            </Card>
          )}
          <TimelineCard history={history} />
        </aside>
      </div>
    </motion.div>
  )
}

function TimelineCard({ history }: { history: ReturnType<typeof useReviewHistory> }) {
  return (
    <Card className="px-4 py-4">
      <p className="text-[13px] font-bold text-ink">Historial</p>
      {history.isPending && <p className="mt-2 text-[12px] text-ink-soft">Cargando historial…</p>}
      {history.isError && (
        <p className="mt-2 text-[12px] text-danger-fg">No se pudo cargar el historial.</p>
      )}
      {history.data && (
        <ul className="mt-2.5 flex flex-col gap-2.5">
          {history.data.events.map((event: WorkflowEventOut) => (
            <li key={event.id} className="text-[12.5px]">
              <p className="font-semibold text-ink">{EVENT_LABELS[event.event_type] ?? event.event_type}</p>
              <p className="text-[11px] text-ink-soft">{formatDate(event.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-ink-soft">
        Timeline append-only: cada transición y decisión queda registrada, nunca se edita.
      </p>
    </Card>
  )
}
