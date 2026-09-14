import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const schema = z.object({
  feedback: z.string().trim().min(1, 'El feedback es obligatorio').max(4000),
})

/** Feedback obligatorio para "Solicitar cambios" (mismo patrón que VersionEditForm). */
export function RequestChangesForm({
  submitting,
  serverError,
  onSubmit,
  onCancel,
}: {
  submitting: boolean
  serverError: string | null
  onSubmit: (feedback: string) => void
  onCancel: () => void
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ feedback: string }>({
    resolver: zodResolver(schema),
    defaultValues: { feedback: '' },
  })

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={handleSubmit((values) => onSubmit(values.feedback))}
      noValidate
    >
      <div>
        <Label htmlFor="review-feedback" className="mb-1.5">
          Feedback para el Creator
        </Label>
        <Textarea
          id="review-feedback"
          rows={4}
          placeholder="Qué debe cambiar en la próxima versión…"
          {...register('feedback')}
        />
        {errors.feedback && (
          <p className="mt-1 text-[11.5px] font-medium text-danger-fg">{errors.feedback.message}</p>
        )}
      </div>
      {serverError && (
        <p role="alert" className="text-[12.5px] font-medium text-danger-fg">
          {serverError}
        </p>
      )}
      <div className="flex justify-end gap-2.5">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={submitting}>
          {submitting ? 'Enviando…' : 'Solicitar cambios'}
        </Button>
      </div>
    </form>
  )
}
