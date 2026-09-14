import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Card } from '@/components/ui/card'
import { ErrorState, LoadingState } from '../../shared/components/StateViews'
import { feedbackItem, surfaceGroup, surfaceItem } from '../../shared/motion'
import type { BrandAssetOut, BrandAssetType } from '../../shared/api/types'
import { useBrandAssets, useDeleteBrandAsset, useUploadBrandAsset } from './brandAssetsApi'

const ACCEPTED_TYPES = 'image/png,image/jpeg,image/webp'

const SLOTS: { type: 'PRIMARY_LOGO' | 'ALT_LOGO'; label: string }[] = [
  { type: 'PRIMARY_LOGO', label: 'Primary Logo' },
  { type: 'ALT_LOGO', label: 'Alternative Logo' },
]

function AssetThumb({
  asset,
  primary,
  multi,
}: {
  asset: BrandAssetOut | null
  primary?: boolean
  multi?: boolean
}) {
  return (
    <div className="clay clay-subtle relative flex h-24 items-center justify-center overflow-hidden bg-tint-steel">
      {primary && (
        <span className="absolute left-2 top-2 rounded-md bg-ink px-2 py-0.5 text-[10px] font-bold text-white">
          Primary
        </span>
      )}
      {asset ? (
        <img
          src={asset.signed_url}
          alt=""
          className="max-h-[70%] max-w-[75%] object-contain"
        />
      ) : multi ? (
        <div className="flex gap-1.5">
          <span className="size-8 rounded-md bg-line" />
          <span className="size-8 rounded-md bg-line/70" />
          <span className="size-8 rounded-md bg-line" />
        </div>
      ) : (
        <span className="size-3 rounded-sm bg-line" aria-hidden="true" />
      )}
    </div>
  )
}

/** Slot único (Primary/Alt Logo): subir crea, subir de nuevo reemplaza. */
function LogoSlotCard({
  type,
  label,
  asset,
  isCreator,
  busy,
  onUpload,
  onDelete,
}: {
  type: 'PRIMARY_LOGO' | 'ALT_LOGO'
  label: string
  asset: BrandAssetOut | null
  isCreator: boolean
  busy: boolean
  onUpload: (type: BrandAssetType, file: File) => void
  onDelete: (assetId: string) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <AssetThumb asset={asset} primary={type === 'PRIMARY_LOGO'} />
      <div className="flex items-center justify-between gap-2 px-3.5 py-3">
        <div className="min-w-0">
          <p className="truncate text-[12.5px] font-semibold text-ink">{label}</p>
          <p className="mt-0.5 text-[11px] text-ink-soft">
            {asset ? 'SVG · Logo' : 'Sin subir'}
          </p>
        </div>
        {isCreator && (
          <div className="flex flex-none items-center gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="text-[11.5px] font-semibold text-steel disabled:opacity-50"
            >
              {asset ? 'Reemplazar' : 'Subir'}
            </button>
            {asset && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onDelete(asset.id)}
                className="text-[11.5px] font-semibold text-danger-fg disabled:opacity-50"
              >
                Eliminar
              </button>
            )}
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="hidden"
        aria-label={asset ? `Reemplazar ${label}` : `Subir ${label}`}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onUpload(type, file)
        }}
      />
    </Card>
  )
}

/** Colección sin límite fijo: cada subida agrega, cada eliminación es individual. */
function VisualReferencesCard({
  assets,
  isCreator,
  busy,
  onUpload,
  onDelete,
}: {
  assets: BrandAssetOut[]
  isCreator: boolean
  busy: boolean
  onUpload: (type: BrandAssetType, file: File) => void
  onDelete: (assetId: string) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <AssetThumb asset={assets[0] ?? null} multi={assets.length > 0} />
      <div className="flex items-center justify-between gap-2 px-3.5 py-3">
        <div className="min-w-0">
          <p className="truncate text-[12.5px] font-semibold text-ink">Visual References</p>
          <p className="mt-0.5 text-[11px] text-ink-soft">
            {assets.length} {assets.length === 1 ? 'image' : 'images'}
          </p>
        </div>
        {isCreator && (
          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            className="flex-none text-[11.5px] font-semibold text-steel disabled:opacity-50"
          >
            Agregar
          </button>
        )}
      </div>
      {isCreator && assets.length > 0 && (
        <ul className="flex flex-wrap gap-2 border-t border-line/60 px-3.5 py-3">
          {assets.map((asset) => (
            <li
              key={asset.id}
              className="clay clay-chip flex items-center gap-1.5 py-1 pl-1 pr-2 text-[11px] text-ink-muted"
            >
              <img src={asset.signed_url} alt="" className="size-5 rounded object-cover" />
              <button
                type="button"
                disabled={busy}
                onClick={() => onDelete(asset.id)}
                aria-label="Eliminar referencia visual"
                className="font-semibold text-danger-fg disabled:opacity-50"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="hidden"
        aria-label="Agregar referencia visual"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onUpload('VISUAL_REFERENCE', file)
        }}
      />
    </Card>
  )
}

/**
 * Sección Brand Assets (change 012): 3 slots -- Primary Logo, Alternative
 * Logo (únicos, reemplazables) y Visual References (colección, cada subida
 * agrega, cada eliminación es individual) -- consumidos también por Visual
 * Compliance como contexto de comparación. Cualquier miembro lee; solo
 * Creator sube/reemplaza/elimina (la autoridad real es el backend, esto solo
 * oculta controles que igual responderían 403).
 */
export function BrandAssetsPanel({ brandId, isCreator }: { brandId: string; isCreator: boolean }) {
  const assets = useBrandAssets(brandId)
  const upload = useUploadBrandAsset(brandId)
  const remove = useDeleteBrandAsset(brandId)
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; message: string } | null>(
    null,
  )

  if (assets.isPending) {
    return <LoadingState label="Cargando Brand Assets…" />
  }
  if (assets.isError) {
    return (
      <ErrorState
        title="No se pudieron cargar los Brand Assets"
        description={
          assets.error instanceof Error ? assets.error.message : 'Error desconocido de la API.'
        }
        onRetry={() => void assets.refetch()}
      />
    )
  }

  const byType = (type: BrandAssetType) => assets.data.assets.filter((a) => a.type === type)
  const primaryLogo = byType('PRIMARY_LOGO')[0] ?? null
  const altLogo = byType('ALT_LOGO')[0] ?? null
  const visualReferences = byType('VISUAL_REFERENCE')

  async function handleUpload(type: BrandAssetType, file: File) {
    setFeedback(null)
    try {
      await upload.mutateAsync({ type, file })
      setFeedback({ kind: 'success', message: 'Brand asset subido correctamente.' })
    } catch (error) {
      setFeedback({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Error al subir el archivo.',
      })
    }
  }

  async function handleDelete(assetId: string) {
    setFeedback(null)
    try {
      await remove.mutateAsync(assetId)
      setFeedback({ kind: 'success', message: 'Brand asset eliminado.' })
    } catch (error) {
      setFeedback({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Error al eliminar el asset.',
      })
    }
  }

  const busy = upload.isPending || remove.isPending

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-4">
      <motion.div variants={surfaceItem}>
        <h2 className="text-[15px] font-bold text-ink">Brand Assets</h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Logo primario, logo alternativo y referencias visuales de la marca.
        </p>
      </motion.div>

      <AnimatePresence>
        {feedback && (
          <motion.p
            key={feedback.message}
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role={feedback.kind === 'error' ? 'alert' : 'status'}
            className={`clay clay-subtle px-4 py-3 text-[13px] font-medium ${
              feedback.kind === 'error'
                ? 'bg-danger-bg text-danger-fg'
                : 'bg-success-bg text-success-fg'
            }`}
          >
            {feedback.message}
          </motion.p>
        )}
      </AnimatePresence>

      <motion.div variants={surfaceItem} className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        {SLOTS.map((slot) => (
          <LogoSlotCard
            key={slot.type}
            type={slot.type}
            label={slot.label}
            asset={slot.type === 'PRIMARY_LOGO' ? primaryLogo : altLogo}
            isCreator={isCreator}
            busy={busy}
            onUpload={handleUpload}
            onDelete={handleDelete}
          />
        ))}
        <VisualReferencesCard
          assets={visualReferences}
          isCreator={isCreator}
          busy={busy}
          onUpload={handleUpload}
          onDelete={handleDelete}
        />
      </motion.div>
    </motion.div>
  )
}
