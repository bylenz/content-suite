import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { motion } from 'motion/react'
import { ApiError } from '../../shared/api/client'
import type { BrandDnaDocument } from '../../shared/api/types'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { PermissionState } from '../../shared/components/StateViews'
import { useActiveBrand } from '../session/useActiveBrand'
import { useSaveDraft } from './api'
import { BrandDnaDocumentForm } from './BrandDnaDocumentForm'
import { emptyDocumentValues } from './documentSchema'

/**
 * Superficie Create Brand DNA: autoría estructurada manual de las cinco
 * secciones del contrato canónico. Guardar crea/actualiza el borrador único
 * de la marca (PATCH); publicar es un paso explícito posterior.
 */
export function BrandDnaCreatePage() {
  const brand = useActiveBrand()
  const navigate = useNavigate()
  const saveDraft = useSaveDraft(brand?.brandId ?? '')
  const [serverError, setServerError] = useState<string | null>(null)

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'CREATOR') {
    return (
      <PermissionState
        title="Creación reservada al Creator"
        description="Solo un Creator puede crear el Brand DNA de la marca. Tu rol actual es de solo lectura."
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
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">Crear Brand DNA</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          Define qué hace única a {brand.brandName}: identidad, voz, comunicación, reglas
          visuales y restricciones. El documento queda como borrador editable.
        </p>
      </motion.div>
      <BrandDnaDocumentForm
        initialDocument={emptyDocumentValues()}
        submitLabel="Guardar borrador"
        submitting={saveDraft.isPending}
        serverError={serverError}
        onSubmit={onSubmit}
        onCancel={() => navigate('/brand-dna')}
      />
    </motion.div>
  )
}
