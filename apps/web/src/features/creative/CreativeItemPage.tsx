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
import { useBrandDna } from '../brand-dna/api'
import { useReviewDetail } from '../approvals/api'
import {
  useAppliedContext,
  useConsistencyCheck,
  useCreativeItem,
  useCreativeVersions,
  useCreateVersion,
  useGenerate,
  useRegenerate,
  useSubmit,
  useVersionDetail,
} from './api'
import { VersionOutputView } from './VersionOutputView'
import { VersionEditForm } from './VersionEditForm'
import { VisualComplianceSection } from './VisualComplianceSection'
import {
  describeMutationError,
  isEditable,
  ORIGIN_VIEW,
  TYPE_VIEW,
  WORKFLOW_STATUS_VIEW,
} from './view'
import type { ConsistencyResultPayload, CreativeOutput } from './types'

/**
 * Editor del ítem creative: contenido de la versión vigente por tipo, acciones
 * del Creator (generar/regenerar, verificación de consistencia, edición humana
 * como versión nueva y submit con confirmación), contexto aplicado (versión
 * exacta de Brand DNA + reglas citadas) e historial inmutable. Los revisores
 * ven solo lectura; los estados 409/503 se presentan por código de envelope.
 */
export function CreativeItemPage() {
  const { itemId = '' } = useParams()
  const brand = useActiveBrand()
  const item = useCreativeItem(itemId)
  const versions = useCreativeVersions(itemId)
  const applied = useAppliedContext(itemId)
  // Para resolver si el contexto aplicado es la versión activa del Brand DNA.
  const brandDna = useBrandDna(brand?.brandId ?? '')
  // Estado y feedback de Content Review (misma fuente que Approvals); el
  // Creator ve la decisión sin ningún control de edición sobre lo enviado.
  const reviewDetail = useReviewDetail(itemId)

  const generate = useGenerate(itemId)
  const regenerate = useRegenerate(itemId)
  const check = useConsistencyCheck(itemId)
  const createVersion = useCreateVersion(itemId)
  const submit = useSubmit(itemId)

  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  // Versión previa abierta read-only desde el historial (spec 04: ver versiones).
  const [viewingVersionId, setViewingVersionId] = useState<string | null>(null)
  const viewedVersion = useVersionDetail(itemId, viewingVersionId)

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (item.isPending) {
    return <LoadingState label="Cargando contenido…" />
  }
  if (item.isError) {
    const error = item.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
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

  const data = item.data
  const status = WORKFLOW_STATUS_VIEW[data.workflow_status]
  const typeView = TYPE_VIEW[data.type]
  const isCreator = brand.role === 'CREATOR'
  const editable = isEditable(data.workflow_status)
  const current = data.current_version
  const hasAiOutput =
    current?.output !== null &&
    (current?.origin === 'AI_GENERATED' || current?.origin === 'AI_REGENERATED')

  function resetActions() {
    setEditing(false)
    setConfirming(false)
    setActionError(null)
  }

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null)
    try {
      await action()
    } catch (error) {
      setActionError(describeMutationError(error))
    }
  }

  const aiPending = generate.isPending || regenerate.isPending
  const anyPending =
    aiPending || check.isPending || createVersion.isPending || submit.isPending

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.header variants={surfaceItem} className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/creative" className="text-[12.5px] font-semibold text-ink-soft hover:text-steel">
            ← Creative Studio
          </Link>
          <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-ink">{data.title}</h1>
            <Badge variant={status.badge}>{status.label}</Badge>
          </div>
          <p className="mt-1 text-[12.5px] text-ink-soft">
            {typeView.label} · v{data.latest_version}
            {current && (
              <>
                {' '}
                · {ORIGIN_VIEW[current.origin].label} · {formatDate(current.created_at)}
              </>
            )}
          </p>
        </div>

        {/* Acciones del Creator solo en estados autorables; el backend manda. */}
        {isCreator && editable && current && (
          <div className="flex flex-wrap gap-2.5">
            <Button
              type="button"
              size="sm"
              onClick={() => void runAction(() => (hasAiOutput ? regenerate.mutateAsync() : generate.mutateAsync()))}
              disabled={anyPending}
            >
              {aiPending
                ? 'Generando…'
                : hasAiOutput
                  ? 'Regenerar con IA'
                  : 'Generar con IA'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setEditing((value) => !value)
                setConfirming(false)
                setEditError(null)
              }}
              disabled={anyPending}
            >
              {editing ? 'Cerrar editor' : 'Editar'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => void runAction(() => check.mutateAsync())}
              disabled={anyPending || current.output === null}
            >
              {check.isPending ? 'Verificando…' : 'Verificar consistencia'}
            </Button>
            {confirming ? (
              <span className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void runAction(async () => {
                    await submit.mutateAsync(current.id)
                    resetActions()
                  })}
                  disabled={anyPending}
                >
                  {submit.isPending ? 'Enviando…' : `Confirmar envío de v${current.version}`}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirming(false)}
                  disabled={anyPending}
                >
                  Cancelar
                </Button>
              </span>
            ) : (
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setConfirming(true)
                  setEditing(false)
                }}
                disabled={anyPending || current.output === null}
              >
                Enviar a revisión
              </Button>
            )}
            {current.output === null && (
              <p className="basis-full text-[11.5px] text-ink-soft">
                Genera con IA o edita el contenido antes de enviarlo a revisión.
              </p>
            )}
          </div>
        )}
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

      {/* Estado enviado: la versión queda congelada hasta la decisión humana. */}
      {data.workflow_status === 'PENDING_CONTENT_REVIEW' && (
        <motion.div
          variants={surfaceItem}
          role="status"
          className="clay clay-subtle bg-warning-bg px-4 py-3 text-[13px] font-medium text-warning-fg"
        >
          Enviado a revisión de contenido. Puedes seguir consultando este contenido; la edición
          permanece bloqueada hasta la decisión del reviewer.
        </motion.div>
      )}
      {data.workflow_status === 'CONTENT_CHANGES_REQUESTED' && (
        <motion.div
          variants={surfaceItem}
          role="status"
          className="clay clay-subtle bg-info-bg px-4 py-3 text-[13px] font-medium text-info-fg"
        >
          <p>
            El reviewer solicitó cambios. Edita o regenera: toda edición crea una versión nueva
            (la anterior permanece inmutable).
          </p>
          {reviewDetail.data?.latest_review?.feedback && (
            <p className="mt-1.5 font-normal italic text-info-fg/90">
              “{reviewDetail.data.latest_review.feedback}”
            </p>
          )}
        </motion.div>
      )}

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Columna editorial: contenido vigente + editor humano */}
        <div className="min-w-0 flex-1 lg:max-w-[740px]">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={editing ? 'editing' : 'viewing'}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className="flex flex-col gap-4"
            >
              {editing && isCreator && editable && current ? (
                <Card className="px-5 py-5">
                  <p className="mb-4 text-[13.5px] font-bold text-ink">
                    Editar contenido — guardará la versión v{data.latest_version + 1}
                  </p>
                  <VersionEditForm
                    contentType={contentTypeFor(data.type)}
                    initialOutput={current.output}
                    submitting={createVersion.isPending}
                    serverError={editError}
                    onSubmit={(output) => {
                      setEditError(null)
                      void createVersion.mutateAsync({ output }).then(resetActions).catch((error) => {
                        setEditError(describeMutationError(error))
                      })
                    }}
                    onCancel={() => {
                      setEditing(false)
                      setEditError(null)
                    }}
                  />
                </Card>
              ) : current?.output ? (
                <Card className="px-5 py-5">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-[13.5px] font-bold text-ink">
                      {current.output.title || data.title}
                    </p>
                    {current.consistency_score !== null && (
                      <Badge variant={current.consistency_score >= 80 ? 'success' : 'warning'} size="sm">
                        Score {current.consistency_score.toFixed(0)}/100
                      </Badge>
                    )}
                  </div>
                  <VersionOutputView output={current.output} />
                </Card>
              ) : (
                <EmptyState
                  title="Sin contenido todavía"
                  description={
                    isCreator
                      ? 'La versión vigente guarda solo el brief. Genera con IA o edita manualmente para crear la primera versión con contenido.'
                      : 'Este ítem aún no tiene contenido generado.'
                  }
                />
              )}
            </motion.div>
          </AnimatePresence>

          {current?.consistency_result && (
            <ConsistencyCard result={current.consistency_result} score={current.consistency_score} />
          )}

          {/* Extensión aditiva (change 008): visual final una vez el contenido
              está aprobado -- upload del Creator, versiones y feedback del
              Visual Reviewer; la decisión y la auditoría viven en Brand Audit. */}
          <VisualComplianceSection
            itemId={data.id}
            workflowStatus={data.workflow_status}
            isCreator={isCreator}
          />

          {/* Vista read-only de una versión previa elegida en el historial. */}
          <AnimatePresence>
            {viewingVersionId && (
              <motion.div key="version-detail" variants={surfaceItem} initial="hidden" animate="show" exit="exit">
                <VersionDetailCard
                  detail={viewedVersion}
                  onClose={() => setViewingVersionId(null)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Columna de contexto: applied context + historial inmutable */}
        <aside className="flex w-full flex-col gap-4 lg:w-[300px] lg:flex-none">
          <AppliedContextCard applied={applied} activeDnaId={brandDna.data?.active?.id ?? null} activeDnaVersion={brandDna.data?.active?.version ?? null} />
          <HistoryCard
            versions={versions}
            latestVersion={data.latest_version}
            selectedVersionId={viewingVersionId}
            onSelect={setViewingVersionId}
          />
        </aside>
      </div>
    </motion.div>
  )
}

function contentTypeFor(type: string): CreativeOutput['content_type'] {
  return type.toLowerCase() as CreativeOutput['content_type']
}

function ConsistencyCard({
  result,
  score,
}: {
  result: ConsistencyResultPayload
  score: number | null
}) {
  const failedFindings = result.findings.filter((finding) => finding.status === 'fail')
  return (
    <Card className="mt-4 px-5 py-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-[13.5px] font-bold text-ink">Verificación de consistencia</p>
        {score !== null && (
          <Badge variant={score >= 80 ? 'success' : 'warning'} size="sm">
            Score {score.toFixed(0)}/100
          </Badge>
        )}
      </div>
      <p className="text-[13px] leading-relaxed text-ink-muted">{result.summary}</p>

      {result.checks.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1.5">
          {result.checks.map((check) => (
            <li key={check.check_id} className="flex items-center justify-between gap-3 text-[12.5px]">
              <span className="min-w-0 truncate text-ink">{check.label}</span>
              <Badge variant={check.status === 'pass' ? 'success' : 'danger'} size="sm">
                {check.status === 'pass' ? 'OK' : 'Falla'}
              </Badge>
            </li>
          ))}
        </ul>
      )}

      {failedFindings.length > 0 && (
        <div className="mt-4 flex flex-col gap-2.5">
          {failedFindings.map((finding) => (
            <div key={`${finding.rule_id}-${finding.category}`} className="clay clay-subtle px-3.5 py-3">
              <p className="flex items-center gap-2 text-[12px] font-semibold text-ink">
                <Badge variant={finding.severity === 'high' ? 'danger' : 'warning'} size="sm">
                  {finding.severity.toUpperCase()}
                </Badge>
                {finding.category}
              </p>
              <p className="mt-1.5 text-[12px] leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Esperado:</span> {finding.expected}
              </p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Detectado:</span> {finding.detected}
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

function AppliedContextCard({
  applied,
  activeDnaId,
  activeDnaVersion,
}: {
  applied: ReturnType<typeof useAppliedContext>
  activeDnaId: string | null
  activeDnaVersion: number | null
}) {
  return (
    <Card className="px-4 py-4">
      <p className="text-[13px] font-bold text-ink">Contexto aplicado</p>
      {applied.isPending && <p className="mt-2 text-[12px] text-ink-soft">Cargando contexto…</p>}
      {applied.isError && (
        <p className="mt-2 text-[12px] text-danger-fg">No se pudo cargar el contexto aplicado.</p>
      )}
      {applied.data && (
        <div className="mt-2.5 flex flex-col gap-2 text-[12.5px] text-ink-muted">
          {applied.data.brand_dna_version_id ? (
            <p>
              <span className="text-ink-soft">Brand DNA: </span>
              {applied.data.brand_dna_version_id === activeDnaId && activeDnaVersion !== null
                ? `versión activa v${activeDnaVersion}`
                : `versión en el momento de generación (${applied.data.brand_dna_version_id.slice(0, 8)}…)`}
            </p>
          ) : (
            <p>
              <span className="text-ink-soft">Brand DNA: </span>sin versión asociada
            </p>
          )}
          <p>
            <span className="text-ink-soft">Reglas aplicadas: </span>
            {applied.data.applied_rule_ids.length > 0
              ? `${applied.data.applied_rule_ids.length} reglas recuperadas (v${applied.data.version})`
              : 'ninguna citada (edición humana)'}
          </p>
          <p className="text-[11.5px] leading-relaxed text-ink-soft">
            El RAG recupera reglas obligatorias y semánticas del Brand Knowledge publicado; los
            embeddings nunca se exponen.
          </p>
        </div>
      )}
    </Card>
  )
}

function HistoryCard({
  versions,
  latestVersion,
  selectedVersionId,
  onSelect,
}: {
  versions: ReturnType<typeof useCreativeVersions>
  latestVersion: number
  selectedVersionId: string | null
  onSelect: (versionId: string | null) => void
}) {
  return (
    <Card className="px-4 py-4">
      <p className="text-[13px] font-bold text-ink">Historial de versiones</p>
      {versions.isPending && <p className="mt-2 text-[12px] text-ink-soft">Cargando historial…</p>}
      {versions.isError && (
        <p className="mt-2 text-[12px] text-danger-fg">No se pudo cargar el historial.</p>
      )}
      {versions.data && (
        <ul className="mt-2.5 flex flex-col gap-2">
          {versions.data.versions.map((version) => {
            const isCurrent = version.version === latestVersion
            const isSelected = version.id === selectedVersionId
            const row = (
              <>
                <span className="min-w-0">
                  <span className="font-semibold text-ink">v{version.version}</span>
                  {isCurrent && (
                    <span className="ml-1.5 text-[10.5px] font-semibold uppercase text-steel">
                      vigente
                    </span>
                  )}
                  <span className="block text-[11px] text-ink-soft">
                    {formatDate(version.created_at)}
                  </span>
                </span>
                <span className="flex flex-none flex-col items-end gap-1">
                  <Badge variant={ORIGIN_VIEW[version.origin].badge} size="sm">
                    {ORIGIN_VIEW[version.origin].label}
                  </Badge>
                  {version.consistency_score !== null && (
                    <span className="text-[10.5px] text-ink-soft">
                      score {version.consistency_score.toFixed(0)}
                    </span>
                  )}
                </span>
              </>
            )
            // La fila vigente ya se muestra en el editor; las previas abren su
            // detalle read-only (spec 04: listar/ver versiones).
            return isCurrent ? (
              <li
                key={version.id}
                className="flex items-center justify-between gap-2 text-[12.5px]"
              >
                {row}
              </li>
            ) : (
              <li key={version.id}>
                <button
                  type="button"
                  aria-label={`Ver versión ${version.version}`}
                  aria-pressed={isSelected}
                  onClick={() => onSelect(isSelected ? null : version.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded-[12px] px-2 py-1.5 text-left text-[12.5px] transition-colors ${
                    isSelected ? 'clay-inset bg-tint-steel' : 'hover:bg-tint-frosted'
                  }`}
                >
                  {row}
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-ink-soft">
        Cada versión es inmutable; la fila vigente es la que se muestra en el editor.
      </p>
    </Card>
  )
}

function VersionDetailCard({
  detail,
  onClose,
}: {
  detail: ReturnType<typeof useVersionDetail>
  onClose: () => void
}) {
  const version = detail.data
  return (
    <Card className="px-5 py-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-[13.5px] font-bold text-ink">
          {version ? `Versión v${version.version} · ${ORIGIN_VIEW[version.origin].label}` : 'Versión anterior'}
        </p>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cerrar
        </Button>
      </div>
      {detail.isPending && <p className="text-[12.5px] text-ink-soft">Cargando versión…</p>}
      {detail.isError && (
        <p className="text-[12.5px] text-danger-fg">No se pudo cargar la versión.</p>
      )}
      {version && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2.5 text-[12px] text-ink-muted">
            {version.consistency_score !== null && (
              <Badge variant={version.consistency_score >= 80 ? 'success' : 'warning'} size="sm">
                Score {version.consistency_score.toFixed(0)}/100
              </Badge>
            )}
            <span>{formatDate(version.created_at)}</span>
            <span className="text-ink-soft">
              {version.brand_dna_version_id
                ? `Brand DNA ${version.brand_dna_version_id.slice(0, 8)}… · ${version.applied_rule_ids.length} reglas aplicadas`
                : 'sin versión de Brand DNA asociada (edición humana)'}
            </span>
            {version.langfuse_trace_id && (
              <span className="text-ink-soft">trace {version.langfuse_trace_id.slice(0, 8)}…</span>
            )}
          </div>
          {version.output ? (
            <VersionOutputView output={version.output} />
          ) : (
            <p className="text-[13px] leading-relaxed text-ink-soft">
              Versión solo con brief: el contenido llegó con la generación o edición siguiente.
            </p>
          )}
        </>
      )}
    </Card>
  )
}
