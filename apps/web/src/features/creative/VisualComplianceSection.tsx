import { useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { formatDate } from '../../shared/format'
import { useUploadVisual, useVisualAssets, useVisualAuditHistory } from '../brand-audit/api'
import { describeVisualError } from '../brand-audit/view'
import type { CreativeWorkflowStatus } from './types'
import { isUploadableVisualStatus, isVisualStage } from './view'

/**
 * Extensión aditiva de Creative Studio (spec 04) para el flujo visual (change
 * 008): el Creator sube el visual final una vez el contenido está aprobado
 * (o tras cambios visuales solicitados), ve el listado de versiones y el
 * feedback del Visual Reviewer. La imagen se muestra siempre vía signed URL,
 * nunca un path interno; la decisión y la auditoría viven en Brand Audit.
 */
export function VisualComplianceSection({
  itemId,
  workflowStatus,
  isCreator,
}: {
  itemId: string
  workflowStatus: CreativeWorkflowStatus
  isCreator: boolean
}) {
  const assets = useVisualAssets(itemId)
  const history = useVisualAuditHistory(itemId)
  const upload = useUploadVisual(itemId)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  if (!isVisualStage(workflowStatus)) {
    return null
  }

  const canUpload = isCreator && isUploadableVisualStatus(workflowStatus)
  const currentAsset = assets.data?.assets[0] ?? null

  // Feedback más reciente del Visual Reviewer para la versión vigente, si existe.
  const latestReview = history.data?.entries
    .flatMap((entry) => entry.reviews)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setUploadError(null)
    try {
      await upload.mutateAsync(file)
    } catch (error) {
      setUploadError(describeVisualError(error))
    }
  }

  return (
    <Card className="mt-4 px-5 py-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-[13.5px] font-bold text-ink">Visual final</p>
        {workflowStatus === 'PENDING_VISUAL_REVIEW' && <Badge variant="warning" size="sm">En revisión visual</Badge>}
        {workflowStatus === 'VISUAL_CHANGES_REQUESTED' && (
          <Badge variant="danger" size="sm">
            Cambios solicitados
          </Badge>
        )}
        {workflowStatus === 'FINAL_APPROVED' && (
          <Badge variant="success" size="sm">
            Aprobado final
          </Badge>
        )}
      </div>

      {currentAsset ? (
        <div className="overflow-hidden rounded-[9px] border border-line">
          <img
            src={currentAsset.signed_url}
            alt={`Visual v${currentAsset.version}`}
            className="max-h-[360px] w-full bg-tint-frosted object-contain"
          />
        </div>
      ) : (
        <p className="text-[13px] leading-relaxed text-ink-soft">
          Todavía no se subió ningún visual para este ítem.
        </p>
      )}

      {latestReview?.decision === 'CHANGES_REQUESTED' && latestReview.feedback && (
        <div className="clay clay-subtle mt-3 bg-info-bg px-4 py-3.5">
          <p className="text-[11px] font-bold uppercase tracking-wide text-info-fg">
            Feedback del Visual Reviewer
          </p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-info-fg">{latestReview.feedback}</p>
        </div>
      )}

      {canUpload && (
        <div className="mt-4 flex flex-col gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => void handleFileChange(event)}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending
              ? 'Subiendo…'
              : currentAsset
                ? 'Subir nueva versión'
                : 'Subir visual final'}
          </Button>
          <p className="text-[11px] text-ink-soft">PNG, JPEG o WebP. El backend valida tipo y tamaño.</p>
          {uploadError && (
            <p role="alert" className="text-[12px] font-medium text-danger-fg">
              {uploadError}
            </p>
          )}
        </div>
      )}

      {assets.data && assets.data.assets.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-ink-soft">
            Versiones del visual
          </p>
          <ul className="flex flex-col gap-1.5">
            {assets.data.assets.map((asset) => (
              <li key={asset.id} className="flex items-center justify-between text-[12.5px] text-ink-muted">
                <span>v{asset.version}</span>
                <span className="text-ink-soft">{formatDate(asset.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

    </Card>
  )
}
