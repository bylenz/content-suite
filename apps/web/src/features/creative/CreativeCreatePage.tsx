import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { PermissionState } from '../../shared/components/StateViews'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { useActiveBrand } from '../session/useActiveBrand'
import { useCreateItem } from './api'
import { describeMutationError, TYPE_VIEW } from './view'
import type { CreativeItemType } from './types'

const VALID_TYPES: CreativeItemType[] = ['PRODUCT_DESCRIPTION', 'VIDEO_SCRIPT', 'IMAGE_PROMPT']

/**
 * Formulario de creación: selector implícito de tipo (viene de la tarjeta),
 * título y brief (objetivo + notas). El brief viaja como dict libre al
 * backend y alimenta la recuperación de Brand Knowledge al generar.
 */
const createSchema = z.object({
  title: z.string().trim().min(1, 'Ingresa un título (máx. 120)').max(120),
  product: z.string().trim().max(200).optional(),
  objective: z.string().trim().min(1, 'Describe el objetivo del contenido').max(2000),
  instructions: z.string().trim().max(2000).optional(),
})

type CreateValues = z.infer<typeof createSchema>

const FIELD_LABELS: Record<CreativeItemType, { product: string; objective: string }> = {
  PRODUCT_DESCRIPTION: { product: 'Producto / oferta', objective: 'Objetivo' },
  VIDEO_SCRIPT: { product: 'Campaña / producto', objective: 'Objetivo' },
  IMAGE_PROMPT: { product: 'Campaña / producto', objective: 'Objetivo visual' },
}

export function CreativeCreatePage() {
  const brand = useActiveBrand()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const createItem = useCreateItem()
  const [serverError, setServerError] = useState<string | null>(null)

  const typeParam = searchParams.get('type') as CreativeItemType | null
  const type = typeParam && VALID_TYPES.includes(typeParam) ? typeParam : null

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateValues>({ resolver: zodResolver(createSchema) })

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'CREATOR') {
    return (
      <PermissionState
        title="Creación reservada al Creator"
        description="Solo un Creator puede crear contenido de la marca. Tu rol actual es de solo lectura."
      />
    )
  }
  if (!type) {
    // Sin tipo válido se vuelve al home de Creative Studio (selección explícita).
    return <Navigate to="/creative" replace />
  }

  async function onSubmit(values: CreateValues) {
    setServerError(null)
    try {
      const brief: Record<string, unknown> = { objective: values.objective }
      if (values.product) brief.product = values.product
      if (values.instructions) brief.instructions = values.instructions
      const item = await createItem.mutateAsync({
        brand_id: brand!.brandId,
        type: type!,
        title: values.title,
        brief,
      })
      navigate(`/creative/items/${item.id}`)
    } catch (error) {
      setServerError(describeMutationError(error))
    }
  }

  const labels = FIELD_LABELS[type]

  return (
    <motion.div variants={surfaceGroup} initial="hidden" animate="show" className="flex flex-col gap-5">
      <motion.div variants={surfaceItem}>
        <Link to="/creative" className="text-[12.5px] font-semibold text-ink-soft hover:text-steel">
          ← Creative Studio
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">
          Crear {TYPE_VIEW[type].label}
        </h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          {TYPE_VIEW[type].description} El brief se guarda como versión 1 y alimenta la generación.
        </p>
      </motion.div>

      <motion.div variants={surfaceItem}>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <Label htmlFor="item-title" className="mb-1.5">
              Título del ítem
            </Label>
            <Input
              id="item-title"
              placeholder="Quinoa Bites Product Description"
              {...register('title')}
            />
            {errors.title && <FieldError message={errors.title.message} />}
          </div>

          <div>
            <Label htmlFor="item-product" className="mb-1.5">
              {labels.product} <span className="text-ink-soft">(opcional)</span>
            </Label>
            <Input id="item-product" placeholder="Quinoa Bites" {...register('product')} />
          </div>

          <div>
            <Label htmlFor="item-objective" className="mb-1.5">
              {labels.objective}
            </Label>
            <Textarea
              id="item-objective"
              rows={3}
              placeholder="Introduce el producto como snack saludable, moderno y conveniente."
              {...register('objective')}
            />
            {errors.objective && <FieldError message={errors.objective.message} />}
          </div>

          <div>
            <Label htmlFor="item-instructions" className="mb-1.5">
              Instrucciones adicionales <span className="text-ink-soft">(opcional)</span>
            </Label>
            <Textarea
              id="item-instructions"
              rows={2}
              placeholder="Enfócate en conveniencia e ingredientes naturales."
              {...register('instructions')}
            />
          </div>

          {serverError && (
            <p role="alert" className="text-[12.5px] font-medium text-danger-fg">
              {serverError}
            </p>
          )}

          <div className="flex justify-end gap-2.5">
            <Button type="button" variant="outline" onClick={() => navigate('/creative')}>
              Cancelar
            </Button>
            <Button type="submit" disabled={createItem.isPending}>
              {createItem.isPending ? 'Creando…' : 'Crear ítem'}
            </Button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="mt-1 text-[11.5px] font-medium text-danger-fg">{message}</p>
}
