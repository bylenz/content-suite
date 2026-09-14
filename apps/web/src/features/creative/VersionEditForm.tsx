import { useFieldArray, useForm, type FieldError, type Resolver } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { CreativeOutput, CreativeSection } from './types'

/**
 * Editor humano: crea una NUEVA versión (HUMAN_EDIT) con la forma exacta del
 * contrato `CreativeOutput` del tipo del ítem. El video script edita
 * secciones heading/body; descripción e imagen editan texto plano.
 */

const sectionSchema = z.object({
  heading: z.string().trim().min(1, 'Sección requiere título').max(120),
  body: z.string().trim().min(1, 'Sección requiere contenido').max(10000),
})

const objectSchema = z.object({
  outputTitle: z.string().trim().min(1, 'El título es obligatorio').max(200),
  content: z.string().trim().max(10000).optional(),
  sections: z.array(sectionSchema).optional(),
})

const videoSchema = objectSchema.refine((values) => (values.sections?.length ?? 0) > 0, {
  message: 'Agrega al menos una sección',
  path: ['sections'],
})

const textSchema = objectSchema.refine((values) => (values.content ?? '') !== '', {
  message: 'El contenido no puede estar vacío',
  path: ['content'],
})

export interface VersionEditValues {
  outputTitle: string
  content?: string
  sections?: CreativeSection[]
}

export function VersionEditForm({
  contentType,
  initialOutput,
  submitting,
  serverError,
  onSubmit,
  onCancel,
}: {
  contentType: CreativeOutput['content_type']
  initialOutput: CreativeOutput | null
  submitting: boolean
  serverError: string | null
  onSubmit: (output: CreativeOutput) => void
  onCancel: () => void
}) {
  const isVideo = contentType === 'video_script'
  // Ambos schemas comparten la misma forma de valores; el cast explícito evita
  // que la unión de ZodEffects degrade la inferencia de useForm.
  const resolver = zodResolver(isVideo ? videoSchema : textSchema) as Resolver<VersionEditValues>
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<VersionEditValues>({
    resolver,
    defaultValues: {
      outputTitle: initialOutput?.title ?? '',
      content: initialOutput?.content ?? '',
      sections: isVideo
        ? (initialOutput?.structured_sections ?? [{ heading: '', body: '' }])
        : [],
    },
  })
  const sectionsArray = useFieldArray({ control, name: 'sections' })

  function buildPayload(values: VersionEditValues): CreativeOutput {
    return {
      content_type: contentType,
      title: values.outputTitle,
      content: isVideo ? null : values.content ?? '',
      structured_sections: isVideo ? (values.sections ?? []) : null,
      // La edición humana no recupera contexto: sin reglas citadas (spec 04).
      applied_rule_ids: [],
    }
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={handleSubmit((values) => onSubmit(buildPayload(values)))}
      noValidate
    >
      <div>
        <Label htmlFor="output-title" className="mb-1.5">
          Título del contenido
        </Label>
        <Input id="output-title" {...register('outputTitle')} />
        {errors.outputTitle && <FieldError error={errors.outputTitle} />}
      </div>

      {isVideo ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <p className="text-[12.5px] font-semibold text-ink">Secciones del guion</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => sectionsArray.append({ heading: '', body: '' })}
            >
              + Sección
            </Button>
          </div>
          {sectionsArray.fields.map((field, index) => (
            <div key={field.id} className="clay clay-subtle flex flex-col gap-2.5 px-4 py-3.5">
              <div className="flex items-center gap-2.5">
                <Input
                  aria-label={`Título de sección ${index + 1}`}
                  placeholder="Hook / desarrollo / cierre…"
                  {...register(`sections.${index}.heading`)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => sectionsArray.remove(index)}
                  aria-label={`Eliminar sección ${index + 1}`}
                >
                  ✕
                </Button>
              </div>
              <Textarea
                aria-label={`Contenido de sección ${index + 1}`}
                rows={2}
                placeholder="Visual y voz en off de esta sección…"
                {...register(`sections.${index}.body`)}
              />
            </div>
          ))}
          {errors.sections && <FieldError error={errors.sections as FieldError} />}
        </div>
      ) : (
        <div>
          <Label htmlFor="output-content" className="mb-1.5">
            Contenido
          </Label>
          <Textarea id="output-content" rows={10} {...register('content')} />
          {errors.content && <FieldError error={errors.content} />}
        </div>
      )}

      {serverError && (
        <p role="alert" className="text-[12.5px] font-medium text-danger-fg">
          {serverError}
        </p>
      )}

      <div className="flex justify-end gap-2.5">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Guardando versión…' : 'Guardar como nueva versión'}
        </Button>
      </div>
    </form>
  )
}

function FieldError({ error }: { error: FieldError }) {
  if (!error?.message) return null
  return <p className="mt-1 text-[11.5px] font-medium text-danger-fg">{error.message}</p>
}
