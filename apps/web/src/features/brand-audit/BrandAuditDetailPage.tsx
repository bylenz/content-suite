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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useActiveBrand } from '../session/useActiveBrand'
import { useCreativeItem } from '../creative/api'
import { TYPE_VIEW, WORKFLOW_STATUS_VIEW } from '../creative/view'
import type { ConsistencyFinding } from '../creative/types'
import {
  useApproveVisual,
  useLatestVisualAudit,
  useRequestVisualChanges,
  useRunVisualAudit,
  useVisualAssets,
  useVisualAuditHistory,
} from './api'
import { SEVERITY_VIEW, describeVisualError, failedFindings, highFailFindings, scoreBadge } from './view'
import type { VisualAssetOut, VisualAuditOut, VisualHistoryEntryOut } from './types'

/**
 * Detalle de Brand Audit: visual vigente vía signed URL (nunca un path),
 * disparo de auditoría multimodal, findings/evidencia por severidad,
 * historial de auditorías/decisiones y panel de decisión (approve con
 * excepción HIGH explícita + confirmación, request-changes con feedback).
 * El score es evidencia asistiva: solo el Visual Reviewer decide (D9).
 */
export function BrandAuditDetailPage() {
  const { itemId = '' } = useParams()
  const brand = useActiveBrand()
  const item = useCreativeItem(itemId)
  const assets = useVisualAssets(itemId)
  const history = useVisualAuditHistory(itemId)

  const currentAsset: VisualAssetOut | null = assets.data?.assets[0] ?? null
  const audit = useLatestVisualAudit(currentAsset?.id ?? null)

  const runAudit = useRunVisualAudit(itemId)
  const approve = useApproveVisual(itemId)
  const requestChanges = useRequestVisualChanges(itemId)

  const [requestingChanges, setRequestingChanges] = useState(false)
  const [confirmingApprove, setConfirmingApprove] = useState(false)
  const [exceptionAccepted, setExceptionAccepted] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

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
  if (item.isPending || assets.isPending) {
    return <LoadingState label="Cargando auditoría visual…" />
  }
  if (item.isError) {
    const error = item.error
    if (error instanceof ApiError && (error.code === 'PERMISSION_DENIED' || error.status === 404)) {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudo cargar el ítem"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void item.refetch()}
      />
    )
  }
  if (assets.isError) {
    return (
      <ErrorState
        title="No se pudieron cargar los visuales"
        description={assets.error instanceof Error ? assets.error.message : 'Error desconocido de la API.'}
        onRetry={() => void assets.refetch()}
      />
    )
  }

  const data = item.data
  const status = WORKFLOW_STATUS_VIEW[data.workflow_status]
  const pending = data.workflow_status === 'PENDING_VISUAL_REVIEW'
  const hasAudit = audit.isSuccess
  const auditData: VisualAuditOut | undefined = audit.data
  const findings: ConsistencyFinding[] = auditData?.findings ?? []
  const failed = failedFindings(findings)
  const highFails = highFailFindings(findings)
  const anyPending = runAudit.isPending || approve.isPending || requestChanges.isPending

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null)
    try {
      await action()
    } catch (error) {
      setActionError(describeVisualError(error))
    }
  }

  function resetActions() {
    setRequestingChanges(false)
    setConfirmingApprove(false)
    setExceptionAccepted(false)
    setFeedback('')
    setActionError(null)
  }

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.header variants={surfaceItem}>
        <Link to="/brand-audit" className="text-[12.5px] font-semibold text-ink-soft hover:text-steel">
          ← Brand Audit
        </Link>
        <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-ink">{data.title}</h1>
          <Badge variant={status.badge}>{status.label}</Badge>
        </div>
        <p className="mt-1 text-[12.5px] text-ink-soft">{TYPE_VIEW[data.type].label}</p>
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

      {!currentAsset ? (
        <EmptyState
          title="Sin visual subido todavía"
          description="Este ítem no tiene ningún visual subido por el Creator para auditar."
        />
      ) : (
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="min-w-0 flex-1 lg:max-w-[640px]">
            <Card className="overflow-hidden p-0">
              <img
                src={currentAsset.signed_url}
                alt={`Visual v${currentAsset.version} de ${data.title}`}
                className="max-h-[520px] w-full bg-tint-frosted object-contain"
              />
              <div className="flex items-center justify-between gap-3 px-5 py-4">
                <p className="text-[13px] font-semibold text-ink">Versión v{currentAsset.version}</p>
                <p className="text-[12px] text-ink-soft">{formatDate(currentAsset.created_at)}</p>
              </div>
            </Card>

            {!hasAudit ? (
              <Card className="mt-4 flex flex-col items-center gap-3 px-6 py-8 text-center">
                <p className="text-[14px] font-bold text-ink">Sin auditar todavía</p>
                <p className="max-w-sm text-[12.5px] leading-relaxed text-ink-muted">
                  Ejecuta la auditoría multimodal para comparar este visual contra las reglas
                  visuales obligatorias del Brand DNA.
                </p>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void runAction(() => runAudit.mutateAsync(currentAsset.id))}
                  disabled={anyPending}
                >
                  {runAudit.isPending ? 'Auditando…' : 'Run Brand Audit'}
                </Button>
              </Card>
            ) : (
              auditData && (
                <FindingsCard
                  audit={auditData}
                  failed={failed}
                  onRerun={() => void runAction(() => runAudit.mutateAsync(currentAsset.id))}
                  rerunning={runAudit.isPending}
                  disabled={anyPending}
                />
              )
            )}
          </div>

          <aside className="flex w-full flex-col gap-4 lg:w-[320px] lg:flex-none">
            {hasAudit && auditData && (
              <Card className="bg-deep px-5 py-5 text-white">
                <p className="text-[11px] font-bold uppercase tracking-wide text-frosted">
                  Brand Compliance
                </p>
                <p className="mt-1.5 text-[30px] font-extrabold tracking-tight">
                  {auditData.score.toFixed(0)} / 100
                </p>
                <Badge variant={scoreBadge(auditData.score)} size="sm" className="mt-1">
                  {auditData.summary}
                </Badge>
                <p className="mt-3 border-t border-white/15 pt-3 text-[11px] leading-relaxed text-frosted">
                  Este score es una señal asistiva. La decisión final es del reviewer.
                </p>
              </Card>
            )}

            {pending && hasAudit && auditData && (
              <DecisionPanel
                highFails={highFails}
                requestingChanges={requestingChanges}
                confirmingApprove={confirmingApprove}
                exceptionAccepted={exceptionAccepted}
                feedback={feedback}
                anyPending={anyPending}
                approving={approve.isPending}
                requestingChangesPending={requestChanges.isPending}
                onFeedbackChange={setFeedback}
                onExceptionChange={setExceptionAccepted}
                onStartRequestChanges={() => {
                  setRequestingChanges(true)
                  setConfirmingApprove(false)
                }}
                onCancelRequestChanges={() => setRequestingChanges(false)}
                onSubmitRequestChanges={() =>
                  void runAction(async () => {
                    await requestChanges.mutateAsync({ auditId: auditData.id, feedback })
                    resetActions()
                  })
                }
                onStartApprove={() => {
                  setConfirmingApprove(true)
                  setRequestingChanges(false)
                }}
                onCancelApprove={() => {
                  setConfirmingApprove(false)
                  setExceptionAccepted(false)
                }}
                onConfirmApprove={() =>
                  void runAction(async () => {
                    await approve.mutateAsync({ auditId: auditData.id, exceptionAccepted })
                    resetActions()
                  })
                }
              />
            )}

            {!pending && data.workflow_status === 'FINAL_APPROVED' && (
              <Card className="bg-deep px-5 py-5 text-white">
                <p className="flex items-center gap-2 text-[14px] font-bold">
                  <span aria-hidden="true">✓</span> Aprobación final completa
                </p>
                <p className="mt-2 text-[12.5px] leading-relaxed text-frosted">
                  Este visual completó el flujo de gobernanza de marca de Content Suite.
                </p>
              </Card>
            )}

            <HistoryCard history={history} />
          </aside>
        </div>
      )}
    </motion.div>
  )
}

function FindingsCard({
  audit,
  failed,
  onRerun,
  rerunning,
  disabled,
}: {
  audit: VisualAuditOut
  failed: ConsistencyFinding[]
  onRerun: () => void
  rerunning: boolean
  disabled: boolean
}) {
  return (
    <Card className="mt-4 px-5 py-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-[13.5px] font-bold text-ink">Audit Findings</p>
        <Button type="button" variant="outline" size="sm" onClick={onRerun} disabled={disabled}>
          {rerunning ? 'Auditando…' : 'Re-run Audit'}
        </Button>
      </div>

      {audit.checks.length > 0 && (
        <ul className="mb-4 flex flex-col gap-1.5">
          {audit.checks.map((check) => (
            <li key={check.check_id} className="flex items-center justify-between gap-3 text-[12.5px]">
              <span className="min-w-0 truncate text-ink">{check.label}</span>
              <Badge variant={check.status === 'pass' ? 'success' : 'danger'} size="sm">
                {check.status === 'pass' ? 'OK' : 'Falla'}
              </Badge>
            </li>
          ))}
        </ul>
      )}

      {failed.length === 0 ? (
        <p className="text-[13px] leading-relaxed text-ink-muted">
          No se detectaron violaciones de marca.
        </p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {failed.map((finding, index) => (
            <div key={`${finding.rule_id}-${index}`} className="clay clay-subtle px-3.5 py-3">
              <div className="flex items-center gap-2">
                <Badge variant={SEVERITY_VIEW[finding.severity].badge} size="sm">
                  {SEVERITY_VIEW[finding.severity].label}
                </Badge>
                <p className="text-[12.5px] font-semibold text-ink">{finding.category}</p>
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Esperado:</span> {finding.expected}
              </p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Detectado:</span> {finding.detected}
              </p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Evidencia:</span> {finding.evidence}
              </p>
              <p className="mt-1 text-[12px] italic leading-relaxed text-ink-soft">
                {finding.recommendation}
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function DecisionPanel({
  highFails,
  requestingChanges,
  confirmingApprove,
  exceptionAccepted,
  feedback,
  anyPending,
  approving,
  requestingChangesPending,
  onFeedbackChange,
  onExceptionChange,
  onStartRequestChanges,
  onCancelRequestChanges,
  onSubmitRequestChanges,
  onStartApprove,
  onCancelApprove,
  onConfirmApprove,
}: {
  highFails: ConsistencyFinding[]
  requestingChanges: boolean
  confirmingApprove: boolean
  exceptionAccepted: boolean
  feedback: string
  anyPending: boolean
  approving: boolean
  requestingChangesPending: boolean
  onFeedbackChange: (value: string) => void
  onExceptionChange: (value: boolean) => void
  onStartRequestChanges: () => void
  onCancelRequestChanges: () => void
  onSubmitRequestChanges: () => void
  onStartApprove: () => void
  onCancelApprove: () => void
  onConfirmApprove: () => void
}) {
  const hasHighFail = highFails.length > 0
  const approveDisabled = anyPending || (hasHighFail && !exceptionAccepted)

  return (
    <Card className="px-5 py-5">
      <p className="mb-3 text-[13px] font-bold text-ink">Visual Review Decision</p>

      {hasHighFail && (
        <p className="clay clay-subtle mb-3 bg-danger-bg px-3.5 py-3 text-[12px] font-semibold text-danger-fg">
          {highFails.length} hallazgo{highFails.length > 1 ? 's' : ''} de severidad HIGH sin resolver.
        </p>
      )}

      {requestingChanges ? (
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="visual-feedback" className="mb-1.5">
              Feedback para el Creator
            </Label>
            <Textarea
              id="visual-feedback"
              rows={4}
              placeholder="Qué debe corregirse en la próxima versión…"
              value={feedback}
              onChange={(event) => onFeedbackChange(event.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2.5">
            <Button type="button" variant="outline" size="sm" onClick={onCancelRequestChanges}>
              Cancelar
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={onSubmitRequestChanges}
              disabled={anyPending || feedback.trim().length === 0}
            >
              {requestingChangesPending ? 'Enviando…' : 'Solicitar cambios'}
            </Button>
          </div>
        </div>
      ) : confirmingApprove ? (
        <div className="flex flex-col gap-3">
          {hasHighFail && (
            <label className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-ink">
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-steel"
                checked={exceptionAccepted}
                onChange={(event) => onExceptionChange(event.target.checked)}
              />
              <span>
                Acepto aprobar este visual a pesar de{' '}
                {highFails.length > 1 ? 'los hallazgos HIGH' : 'el hallazgo HIGH'} sin resolver. Esta
                excepción queda registrada con la evidencia del finding.
              </span>
            </label>
          )}
          <p className="text-[12.5px] leading-relaxed text-ink-muted">
            Confirmas que este visual pasa a <strong>Final Approved</strong>.
          </p>
          <div className="flex justify-end gap-2.5">
            <Button type="button" variant="outline" size="sm" onClick={onCancelApprove}>
              Cancelar
            </Button>
            <Button type="button" size="sm" onClick={onConfirmApprove} disabled={approveDisabled}>
              {approving ? 'Aprobando…' : 'Confirmar aprobación'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Button type="button" size="sm" onClick={onStartApprove} disabled={anyPending}>
            Approve Visual
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={onStartRequestChanges} disabled={anyPending}>
            Request Changes
          </Button>
        </div>
      )}
    </Card>
  )
}

const EVENT_LABELS: Record<string, string> = {
  VISUAL_UPLOADED: 'Visual subido',
  FINAL_APPROVED: 'Aprobado final',
  VISUAL_CHANGES_REQUESTED: 'Cambios solicitados',
}

function HistoryCard({ history }: { history: ReturnType<typeof useVisualAuditHistory> }) {
  return (
    <Card className="px-4 py-4">
      <p className="text-[13px] font-bold text-ink">Historial de auditoría</p>
      {history.isPending && <p className="mt-2 text-[12px] text-ink-soft">Cargando historial…</p>}
      {history.isError && (
        <p className="mt-2 text-[12px] text-danger-fg">No se pudo cargar el historial.</p>
      )}
      {history.data && (
        <ul className="mt-2.5 flex flex-col gap-3">
          {history.data.entries.map((entry: VisualHistoryEntryOut) => (
            <li key={entry.asset.id} className="border-t border-line pt-2.5 first:border-t-0 first:pt-0">
              <p className="text-[12.5px] font-semibold text-ink">Versión v{entry.asset.version}</p>
              {entry.audits.map((a) => (
                <p key={a.id} className="mt-1 text-[11.5px] text-ink-soft">
                  Auditoría · score {a.score.toFixed(0)} · {formatDate(a.created_at)}
                </p>
              ))}
              {entry.reviews.map((r) => (
                <p key={r.id} className="mt-1 text-[11.5px] text-ink-soft">
                  {EVENT_LABELS[r.decision === 'APPROVED' ? 'FINAL_APPROVED' : 'VISUAL_CHANGES_REQUESTED']}
                  {' · '}
                  {formatDate(r.created_at)}
                  {r.exception_accepted && ' · excepción HIGH aceptada'}
                </p>
              ))}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-ink-soft">
        Cada versión, auditoría y decisión queda registrada de forma append-only.
      </p>
    </Card>
  )
}
