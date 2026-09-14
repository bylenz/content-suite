import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import type { BrandDnaDocument } from '../../shared/api/types'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { ErrorState, LoadingState, PermissionState } from '../../shared/components/StateViews'
import { useActiveBrand } from '../session/useActiveBrand'
import { useBrandDna, useSaveDraft } from './api'
import { BrandDnaDocumentForm } from './BrandDnaDocumentForm'
import { documentToFormValues } from './documentSchema'

/**
 * Edición del borrador: opera sobre el borrador vigente (o inicializa uno
 * nuevo desde la versión activa al guardar; el backend resuelve el upsert).
 * PATCH es reemplazo completo del documento del borrador.
 */
export function BrandDnaEditPage() {
  const brand = useActiveBrand()
  const navigate = useNavigate()
  const overview = useBrandDna(brand?.brandId ?? '')
  const saveDraft = useSaveDraft(brand?.brandId ?? '')
  const [serverError, setServerError] = useState<string | null>(null)

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'CREATOR') {
    return (
      <PermissionState
        title="Edición reservada al Creator"
        description="Solo un Creator puede editar el borrador del Brand DNA. Tu rol actual es de solo lectura."
      />
    )
  }

  if (overview.isPending) {
    return <LoadingState label="Cargando borrador…" />
  }
  if (overview.isError) {
    return (
      <ErrorState
        title="No se pudo cargar el documento"
        description={overview.error instanceof Error ? overview.error.message : 'Error de la API.'}
        onRetry={() => void overview.refetch()}
      />
    )
  }

  const { draft, active } = overview.data
  // Se edita el borrador si existe; si no, se parte del documento activo
  // (el backend creará la siguiente versión como DRAFT al guardar).
  const base = draft ?? active
  if (!base) {
    // Sin documento base no hay nada que editar: la creación es la vía.
    return (
      <PermissionState
        title="No hay documento para editar"
        description="Esta marca aún no tiene Brand DNA. Crea el documento primero."
      />
    )
  }

  async function onSubmit(document: BrandDnaDocument) {
    setServerError(null)
    try {
      await saveDraft.mutateAsync(document)
      navigate('/brand-dna')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
        const fields = error.details?.['field_errors']
        setServerError(
          `La API rechazó el documento: ${
            Array.isArray(fields) ? fields.join(', ') : error.message
          }`,
        )
      } else {
        setServerError(error instanceof Error ? error.message : 'Error al guardar el borrador.')
      }
    }
  }

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
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">
          {draft ? `Editar borrador · v${draft.version}` : 'Editar y crear nuevo borrador'}
        </h1>
        {!draft && active && (
          <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
            Guardar creará el borrador v{active.version + 1} inicializado con el documento
            activo v{active.version} y tus cambios. La versión activa no se modifica.
          </p>
        )}
      </motion.div>
      <BrandDnaDocumentForm
        initialDocument={documentToFormValues(base.document)}
        submitLabel={draft ? 'Guardar cambios del borrador' : 'Crear borrador'}
        submitting={saveDraft.isPending}
        serverError={serverError}
        onSubmit={onSubmit}
        onCancel={() => navigate('/brand-dna')}
      />
    </motion.div>
  )
}
