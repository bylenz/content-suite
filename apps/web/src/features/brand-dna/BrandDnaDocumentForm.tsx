import { cloneElement, isValidElement, useId, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useFieldArray, useForm, type FieldError, type Path, type UseFormGetValues, type UseFormRegister, type UseFormRegisterReturn, type UseFormSetValue } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { BrandDnaDocument } from '../../shared/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { feedbackItem, surfaceGroup, surfaceItem } from '../../shared/motion'
import {
  brandDnaDocumentSchema,
  type BrandDnaDocumentFormValues,
} from './documentSchema'
import { FIELD_LABELS, FIELD_LIMITS, SECTIONS, sectionTitle } from './sections'

/**
 * Formulario de autoría estructurada del documento Brand DNA con React Hook
 * Form + Zod (esquema espejo estricto del contrato canónico). Lo comparten la
 * creación manual (`/brand-dna/create`) y la edición del borrador
 * (`/brand-dna/edit`). Mensajes de error por campo y por sección.
 */

function FieldErrorText({ error, id }: { error: FieldError | undefined; id?: string }) {
  if (!error) return null
  return (
    <p role="alert" id={id} className="mt-1 text-xs font-medium text-danger-fg">
      {error.message}
    </p>
  )
}

function FieldShell({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: string
  error: FieldError | undefined
  children: React.ReactNode
}) {
  // Asociación programática label ↔ control: el id único se inyecta en el
  // único hijo (Input/Textarea) y el error se anuncia vía aria-describedby.
  const fieldId = useId()
  const errorId = `${fieldId}-error`
  const control =
    isValidElement(children)
      ? cloneElement(children as React.ReactElement<Record<string, unknown>>, {
          id: fieldId,
          'aria-describedby': error ? errorId : undefined,
        })
      : children
  return (
    <div>
      <Label htmlFor={fieldId} className="mb-1.5">
        {label}
        {hint && <span className="ml-1.5 font-normal text-ink-soft">({hint})</span>}
      </Label>
      {control}
      <FieldErrorText id={errorId} error={error} />
    </div>
  )
}

function SectionCard({
  step,
  title,
  description,
  children,
  id,
}: {
  step: number
  title: string
  description: string
  children: React.ReactNode
  id?: string
}) {
  // Entrada única al montar (opacidad + desplazamiento mínimo): la edición
  // por teclado nunca re-anima porque el card no se desmonta.
  return (
    <motion.section
      id={id}
      variants={surfaceItem}
      className="clay clay-card flex scroll-mt-6 flex-col gap-4 p-6"
    >
      <header className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className="grid size-[22px] place-items-center rounded-md bg-frosted text-[11px] font-bold text-ink"
        >
          {step}
        </span>
        <div>
          <h2 className="text-[14px] font-bold text-ink">{title}</h2>
          <p className="text-[12px] text-ink-soft">{description}</p>
        </div>
      </header>
      {children}
    </motion.section>
  )
}

function ListLabel({ label, range, hint }: { label: string; range: string; hint: string }) {
  return (
    <p className="mb-1.5 text-[12px] font-semibold text-ink-muted">
      {label}
      <span className="ml-1.5 font-normal text-ink-soft">
        ({range} · {hint})
      </span>
    </p>
  )
}

/**
 * Editor de lista de strings. Los valores viven en RHF (`register` por índice);
 * el conteo de filas es estado local que redibuja al agregar/quitar.
 * ponytail: RHF 7.88 excluye arrays de primitivos de FieldArrayPath, así que
 * useFieldArray no tipa para listas de strings; register+setValue sí, y los
 * límites por item los valida el esquema Zod compartido.
 */
function StringListEditor({
  name,
  label,
  range,
  hint,
  minRows,
  max,
  placeholder,
  addLabel,
  register,
  getValues,
  setValue,
  rowError,
  rootError,
}: {
  name: Path<BrandDnaDocumentFormValues>
  label: string
  range: string
  hint: string
  minRows: number
  max: number
  placeholder: string
  addLabel: string
  register: UseFormRegister<BrandDnaDocumentFormValues>
  getValues: UseFormGetValues<BrandDnaDocumentFormValues>
  setValue: UseFormSetValue<BrandDnaDocumentFormValues>
  rowError: (index: number) => FieldError | undefined
  rootError: FieldError | undefined
}) {
  const [rows, setRows] = useState(() => {
    const current = getValues(name)
    return Math.max(minRows, Array.isArray(current) ? current.length : 0)
  })

  function registerRow(index: number): UseFormRegisterReturn {
    // Ruta dinámica `name.N`: el cast localiza la única aserción de tipos.
    return register(`${name}.${index}` as Path<BrandDnaDocumentFormValues>)
  }

  function append() {
    const current = (getValues(name) as string[] | undefined) ?? []
    setValue(name, [...current, ''] as never, { shouldDirty: true })
    setRows((r) => r + 1)
  }

  function remove(index: number) {
    const current = (getValues(name) as string[] | undefined) ?? []
    const next = current.filter((_, i) => i !== index)
    setValue(name, next as never, { shouldDirty: true })
    setRows((r) => Math.max(minRows, r - 1))
  }

  return (
    <div>
      <ListLabel label={label} range={range} hint={hint} />
      <ul className="flex flex-col gap-2">
        {Array.from({ length: rows }, (_, index) => {
          // id determinista por ruta+índice: única por lista y fila.
          const rowId = `field-${String(name).replace(/\./g, '-')}-${index}`
          const rowFieldError = rowError(index)
          return (
            <li key={`${name}-${index}`} className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                <Input
                  {...registerRow(index)}
                  id={rowId}
                  aria-label={`${label} ${index + 1}`}
                  aria-describedby={rowFieldError ? `${rowId}-error` : undefined}
                  placeholder={placeholder}
                />
                <FieldErrorText id={`${rowId}-error`} error={rowFieldError} />
              </div>
              <Button
                type="button"
                variant="destructive"
                size="chip"
                onClick={() => remove(index)}
                disabled={rows <= minRows}
                className="mt-0.5"
              >
                Quitar<span className="sr-only"> este elemento</span>
              </Button>
            </li>
          )
        })}
      </ul>
      <FieldErrorText error={rootError} />
      <Button type="button" variant="ghost" onClick={append} disabled={rows >= max} className="mt-2 text-[12px]">
        + {addLabel}
      </Button>
    </div>
  )
}

export function BrandDnaDocumentForm({
  initialDocument,
  submitLabel,
  submitting,
  serverError,
  onSubmit,
  onCancel,
}: {
  initialDocument: BrandDnaDocumentFormValues
  submitLabel: string
  submitting: boolean
  serverError: string | null
  onSubmit: (document: BrandDnaDocument) => Promise<void> | void
  onCancel: () => void
}) {
  // Sin genéricos explícitos: la inferencia fluye desde zodResolver (patrón
  // documentado de RHF). El resolver entrega al submit los valores ya
  // recortados por el esquema espejo.
  const {
    register,
    control,
    handleSubmit,
    getValues,
    setValue,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(brandDnaDocumentSchema),
    defaultValues: initialDocument,
    mode: 'onSubmit',
  })

  // Array de objetos: soporte tipado completo de useFieldArray.
  const pillars = useFieldArray({ control, name: 'communication.message_pillars' })

  const listProps = { register, getValues, setValue }

  return (
    <form onSubmit={handleSubmit((values) => void onSubmit(values))} noValidate>
      <motion.div
        variants={surfaceGroup}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4.5"
      >
        {/* 1. Identidad */}
        <SectionCard
          id="section-identity"
          step={1}
          title={sectionTitle('identity')}
          description={SECTIONS[0].description}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <FieldShell
              label={FIELD_LABELS.identity.purpose}
              hint={FIELD_LIMITS.narrative}
              error={errors.identity?.purpose}
            >
              <Textarea
                rows={3}
                {...register('identity.purpose')}
                placeholder="Para qué existe la marca…"
              />
            </FieldShell>
            <FieldShell
              label={FIELD_LABELS.identity.positioning}
              hint={FIELD_LIMITS.narrative}
              error={errors.identity?.positioning}
            >
              <Textarea
                rows={3}
                {...register('identity.positioning')}
                placeholder="Cómo se posiciona frente a su mercado…"
              />
            </FieldShell>
          </div>
          <StringListEditor
            {...listProps}
            name="identity.personality_traits"
            label={FIELD_LABELS.identity.personality_traits}
            range="1–8 etiquetas"
            hint={FIELD_LIMITS.label}
            minRows={1}
            max={8}
            placeholder="p. ej. Cercana"
            addLabel="Agregar rasgo"
            rowError={(index) => errors.identity?.personality_traits?.[index]}
            rootError={errors.identity?.personality_traits?.root}
          />
          <FieldShell
            label={FIELD_LABELS.identity.audience}
            hint={FIELD_LIMITS.narrative}
            error={errors.identity?.audience}
          >
            <Textarea
              rows={2}
              {...register('identity.audience')}
              placeholder="A quién habla la marca…"
            />
          </FieldShell>
        </SectionCard>

        {/* 2. Voz */}
        <SectionCard
          id="section-voice"
          step={2}
          title={sectionTitle('voice')}
          description={SECTIONS[1].description}
        >
          <StringListEditor
            {...listProps}
            name="voice.tone_characteristics"
            label={FIELD_LABELS.voice.tone_characteristics}
            range="1–8 etiquetas"
            hint={FIELD_LIMITS.label}
            minRows={1}
            max={8}
            placeholder="p. ej. Cálida"
            addLabel="Agregar característica"
            rowError={(index) => errors.voice?.tone_characteristics?.[index]}
            rootError={errors.voice?.tone_characteristics?.root}
          />
          <FieldShell
            label={FIELD_LABELS.voice.usage_guide}
            hint={FIELD_LIMITS.guide}
            error={errors.voice?.usage_guide}
          >
            <Textarea
              rows={3}
              {...register('voice.usage_guide')}
              placeholder="Cómo debe sonar la marca al escribir…"
            />
          </FieldShell>
          <div className="grid gap-4 md:grid-cols-2">
            <StringListEditor
              {...listProps}
              name="voice.preferred_vocabulary"
              label={FIELD_LABELS.voice.preferred_vocabulary}
              range="0–30 términos"
              hint={FIELD_LIMITS.label}
              minRows={0}
              max={30}
              placeholder="p. ej. real"
              addLabel="Agregar término"
              rowError={(index) => errors.voice?.preferred_vocabulary?.[index]}
              rootError={errors.voice?.preferred_vocabulary?.root}
            />
            <StringListEditor
              {...listProps}
              name="voice.avoid_vocabulary"
              label={FIELD_LABELS.voice.avoid_vocabulary}
              range="0–30 términos"
              hint={FIELD_LIMITS.label}
              minRows={0}
              max={30}
              placeholder="p. ej. barato"
              addLabel="Agregar término"
              rowError={(index) => errors.voice?.avoid_vocabulary?.[index]}
              rootError={errors.voice?.avoid_vocabulary?.root}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <StringListEditor
              {...listProps}
              name="voice.do_examples"
              label={FIELD_LABELS.voice.do_examples}
              range="1–10 ejemplos"
              hint={FIELD_LIMITS.example}
              minRows={1}
              max={10}
              placeholder="p. ej. Di: …"
              addLabel="Agregar ejemplo"
              rowError={(index) => errors.voice?.do_examples?.[index]}
              rootError={errors.voice?.do_examples?.root}
            />
            <StringListEditor
              {...listProps}
              name="voice.dont_examples"
              label={FIELD_LABELS.voice.dont_examples}
              range="1–10 ejemplos"
              hint={FIELD_LIMITS.example}
              minRows={1}
              max={10}
              placeholder="p. ej. Evita: …"
              addLabel="Agregar ejemplo"
              rowError={(index) => errors.voice?.dont_examples?.[index]}
              rootError={errors.voice?.dont_examples?.root}
            />
          </div>
        </SectionCard>

        {/* 3. Comunicación */}
        <SectionCard
          id="section-communication"
          step={3}
          title={sectionTitle('communication')}
          description={SECTIONS[2].description}
        >
          <div>
            <ListLabel
              label={FIELD_LABELS.communication.message_pillars}
              range="1–5 pilares"
              hint="nombre + descripción"
            />
            <ul className="flex flex-col gap-3">
              {pillars.fields.map((field, index) => {
                const nameId = `pillar-${field.id}-name`
                const descriptionId = `pillar-${field.id}-description`
                const nameFieldError = errors.communication?.message_pillars?.[index]?.name
                const descriptionFieldError =
                  errors.communication?.message_pillars?.[index]?.description
                return (
                  <li key={field.id} className="clay clay-subtle flex flex-col gap-2 p-3.5">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <Input
                          {...register(`communication.message_pillars.${index}.name`)}
                          id={nameId}
                          aria-label={`Pilar ${index + 1}: nombre`}
                          aria-describedby={nameFieldError ? `${nameId}-error` : undefined}
                          placeholder={`Nombre del pilar (${FIELD_LIMITS.pillarName})`}
                        />
                        <FieldErrorText id={`${nameId}-error`} error={nameFieldError} />
                      </div>
                      <Button
                        type="button"
                        variant="destructive"
                        size="chip"
                        onClick={() => pillars.remove(index)}
                        disabled={pillars.fields.length <= 1}
                        className="mt-0.5"
                      >
                        Quitar pilar
                      </Button>
                    </div>
                    <div>
                      <Textarea
                        rows={2}
                        {...register(`communication.message_pillars.${index}.description`)}
                        id={descriptionId}
                        aria-label={`Pilar ${index + 1}: descripción`}
                        aria-describedby={descriptionFieldError ? `${descriptionId}-error` : undefined}
                        placeholder={`Descripción (${FIELD_LIMITS.example})`}
                      />
                      <FieldErrorText id={`${descriptionId}-error`} error={descriptionFieldError} />
                    </div>
                  </li>
                )
              })}
            </ul>
            <FieldErrorText error={errors.communication?.message_pillars?.root} />
            <Button
              type="button"
              variant="ghost"
              onClick={() => pillars.append({ name: '', description: '' })}
              disabled={pillars.fields.length >= 5}
              className="mt-2 text-[12px]"
            >
              + Agregar pilar
            </Button>
          </div>
          <StringListEditor
            {...listProps}
            name="communication.rules"
            label={FIELD_LABELS.communication.rules}
            range="1–20 reglas"
            hint={FIELD_LIMITS.rule}
            minRows={1}
            max={20}
            placeholder="p. ej. Siempre cierra con una llamada a la acción"
            addLabel="Agregar regla"
            rowError={(index) => errors.communication?.rules?.[index]}
            rootError={errors.communication?.rules?.root}
          />
        </SectionCard>

        {/* 4. Reglas visuales */}
        <SectionCard
          id="section-visual_rules"
          step={4}
          title={sectionTitle('visual_rules')}
          description={SECTIONS[3].description}
        >
          <div className="grid gap-4 md:grid-cols-2">
            {(
              [
                ['visual_personality', FIELD_LABELS.visual_rules.visual_personality],
                ['imagery_direction', FIELD_LABELS.visual_rules.imagery_direction],
                ['composition', FIELD_LABELS.visual_rules.composition],
                ['logo_usage', FIELD_LABELS.visual_rules.logo_usage],
              ] as const
            ).map(([name, label]) => (
              <FieldShell
                key={name}
                label={label}
                hint={FIELD_LIMITS.narrative}
                error={errors.visual_rules?.[name]}
              >
                <Textarea rows={3} {...register(`visual_rules.${name}`)} />
              </FieldShell>
            ))}
          </div>
        </SectionCard>

        {/* 5. Restricciones */}
        <SectionCard
          id="section-restrictions"
          step={5}
          title={sectionTitle('restrictions')}
          description={SECTIONS[4].description}
        >
          <StringListEditor
            {...listProps}
            name="restrictions.rules"
            label={FIELD_LABELS.restrictions.rules}
            range="1–20 reglas"
            hint={FIELD_LIMITS.rule}
            minRows={1}
            max={20}
            placeholder="p. ej. Nunca uses términos médicos"
            addLabel="Agregar restricción"
            rowError={(index) => errors.restrictions?.rules?.[index]}
            rootError={errors.restrictions?.rules?.root}
          />
        </SectionCard>
      </motion.div>

      <AnimatePresence>
        {serverError && (
          <motion.p
            key="form-server-error"
            variants={feedbackItem}
            initial="hidden"
            animate="show"
            exit="exit"
            role="alert"
            className="clay clay-subtle mt-5 bg-danger-bg px-4 py-3 text-[13px] font-medium text-danger-fg"
          >
            {serverError}
          </motion.p>
        )}
      </AnimatePresence>

      <div className="mt-6 flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-md text-[12.5px] leading-relaxed text-ink-soft">
          El documento se guarda como borrador de la marca; publicar es un paso
          explícito posterior.
        </p>
        <div className="flex gap-2.5">
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={onCancel}
            className="px-4.5 text-[13.5px]"
          >
            Cancelar
          </Button>
          <Button type="submit" size="lg" disabled={submitting}>
            {submitting ? 'Guardando…' : submitLabel}
          </Button>
        </div>
      </div>
    </form>
  )
}
