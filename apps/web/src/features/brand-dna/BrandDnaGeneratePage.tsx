import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { motion } from 'motion/react'
import {
  useForm,
  type FieldError,
  type Path,
  type UseFormGetValues,
  type UseFormRegister,
  type UseFormSetValue,
} from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ApiError } from '../../shared/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { AnimatePresence } from 'motion/react'
import { feedbackItem, surfaceGroup, surfaceItem } from '../../shared/motion'
import { PermissionState } from '../../shared/components/StateViews'
import { useActiveBrand } from '../session/useActiveBrand'
import { useGenerateBrandDna } from './api'
import {
  TONE_PRESETS,
  brandBriefSchema,
  emptyBriefValues,
  type BrandBriefFormValues,
  type BrandBriefValidated,
} from './briefSchema'

/**
 * Pantalla de brief de onboarding ("Create Brand DNA" en
 * `starter-design/Content Suite.dc.html`): Brand Basics, Audience,
 * Personality & Tone y Brand Rules. "Generate Brand DNA" invoca
 * `POST .../brand-dna/generate`; el resultado aterriza en `/brand-dna`
 * (el DRAFT generado, para revisión humana) — mismo destino que la autoría
 * manual al guardar.
 */

function FieldErrorText({ error }: { error: FieldError | undefined }) {
  if (!error) return null
  return (
    <p role="alert" className="mt-1 text-xs font-medium text-danger-fg">
      {error.message}
    </p>
  )
}

function SectionCard({
  step,
  title,
  description,
  children,
}: {
  step: number
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-4 p-6">
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

/**
 * Lista de tags/chips removibles con entrada libre (rasgos de personalidad,
 * tags de audiencia). Los presets (si hay) son atajos que agregan al mismo
 * arreglo; no son un valor distinto.
 */
function ChipListField({
  name,
  label,
  hint,
  max,
  maxItemLength,
  placeholder,
  presets,
  getValues,
  setValue,
  error,
}: {
  name: Path<BrandBriefFormValues>
  label: string
  hint: string
  max: number
  maxItemLength: number
  placeholder: string
  presets?: readonly string[]
  getValues: UseFormGetValues<BrandBriefFormValues>
  setValue: UseFormSetValue<BrandBriefFormValues>
  error: FieldError | undefined
}) {
  const [draft, setDraft] = useState('')
  const [, forceRender] = useState(0)

  function current(): string[] {
    return (getValues(name) as string[] | undefined) ?? []
  }

  function add(value: string) {
    const trimmedValue = value.trim()
    if (!trimmedValue) return
    const existing = current()
    if (existing.includes(trimmedValue) || existing.length >= max) return
    setValue(name, [...existing, trimmedValue] as never, { shouldDirty: true, shouldValidate: true })
    forceRender((n) => n + 1)
  }

  function remove(value: string) {
    setValue(name, current().filter((item) => item !== value) as never, {
      shouldDirty: true,
      shouldValidate: true,
    })
    forceRender((n) => n + 1)
  }

  const selected = current()

  return (
    <div>
      <p className="mb-1.5 text-[12px] font-semibold text-ink-muted">
        {label}
        <span className="ml-1.5 font-normal text-ink-soft">({hint})</span>
      </p>
      {presets && presets.length > 0 && (
        <div className="mb-2.5 flex flex-wrap gap-1.5">
          {presets.map((preset) => (
            <Button
              key={preset}
              type="button"
              size="chip"
              variant={selected.includes(preset) ? 'default' : 'outline'}
              onClick={() => (selected.includes(preset) ? remove(preset) : add(preset))}
            >
              {preset}
            </Button>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5" aria-label={`${label} seleccionados`}>
          {selected.map((item) => (
            <li key={item}>
              <Button type="button" size="chip" variant="secondary" onClick={() => remove(item)}>
                {item} <span aria-hidden="true">×</span>
                <span className="sr-only"> quitar</span>
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input
          value={draft}
          maxLength={maxItemLength}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              add(draft)
              setDraft('')
            }
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            add(draft)
            setDraft('')
          }}
          disabled={selected.length >= max}
        >
          Agregar
        </Button>
      </div>
      <FieldErrorText error={error} />
    </div>
  )
}

/** Lista de reglas (always/never): filas de texto libre, sin límite de líneas. */
function RuleListEditor({
  name,
  label,
  min,
  max,
  placeholder,
  addLabel,
  register,
  getValues,
  setValue,
  rowError,
  rootError,
}: {
  name: Path<BrandBriefFormValues>
  label: string
  min: number
  max: number
  placeholder: string
  addLabel: string
  register: UseFormRegister<BrandBriefFormValues>
  getValues: UseFormGetValues<BrandBriefFormValues>
  setValue: UseFormSetValue<BrandBriefFormValues>
  rowError: (index: number) => FieldError | undefined
  rootError: FieldError | undefined
}) {
  const [rows, setRows] = useState(() => {
    const current = getValues(name)
    return Math.max(min, Array.isArray(current) ? current.length : 0)
  })

  function append() {
    const current = (getValues(name) as string[] | undefined) ?? []
    setValue(name, [...current, ''] as never, { shouldDirty: true })
    setRows((r) => r + 1)
  }

  function remove(index: number) {
    const current = (getValues(name) as string[] | undefined) ?? []
    setValue(name, current.filter((_, i) => i !== index) as never, { shouldDirty: true })
    setRows((r) => Math.max(min, r - 1))
  }

  return (
    <div>
      <p className="mb-1.5 text-[12px] font-semibold text-ink-muted">{label}</p>
      <ul className="flex flex-col gap-2">
        {Array.from({ length: rows }, (_, index) => (
          <li key={`${name}-${index}`} className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <Input
                {...register(`${name}.${index}` as Path<BrandBriefFormValues>)}
                aria-label={`${label} ${index + 1}`}
                placeholder={placeholder}
              />
              <FieldErrorText error={rowError(index)} />
            </div>
            <Button
              type="button"
              variant="destructive"
              size="chip"
              onClick={() => remove(index)}
              disabled={rows <= min}
              className="mt-0.5"
            >
              Quitar
            </Button>
          </li>
        ))}
      </ul>
      <FieldErrorText error={rootError} />
      <Button
        type="button"
        variant="ghost"
        onClick={append}
        disabled={rows >= max}
        className="mt-2 text-[12px]"
      >
        + {addLabel}
      </Button>
    </div>
  )
}

export function BrandDnaGeneratePage() {
  const brand = useActiveBrand()
  const navigate = useNavigate()
  const generateBrandDna = useGenerateBrandDna(brand?.brandId ?? '')
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    getValues,
    setValue,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(brandBriefSchema),
    defaultValues: emptyBriefValues(),
    mode: 'onSubmit',
  })

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }
  if (brand.role !== 'CREATOR') {
    return (
      <PermissionState
        title="Generación reservada al Creator"
        description="Solo un Creator puede generar el Brand DNA de la marca a partir de un brief."
      />
    )
  }

  async function onSubmit(brief: BrandBriefValidated) {
    setServerError(null)
    try {
      await generateBrandDna.mutateAsync(brief)
      navigate('/brand-dna')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'SERVICE_UNAVAILABLE') {
        setServerError(
          'La generación no está disponible en este momento (proveedor de IA no configurado). Intenta de nuevo más tarde o crea el Brand DNA manualmente.',
        )
      } else if (error instanceof ApiError && error.code === 'AI_OUTPUT_INVALID') {
        setServerError('El modelo no produjo un documento válido. Intenta generar de nuevo.')
      } else if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
        const fields = error.details?.['field_errors']
        setServerError(
          `La API rechazó el brief: ${Array.isArray(fields) ? fields.join(', ') : error.message}`,
        )
      } else {
        setServerError(error instanceof Error ? error.message : 'Error al generar el Brand DNA.')
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
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">Crear Brand DNA con IA</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-muted">
          Cuéntanos qué hace única a {brand.brandName}. La IA transformará este brief en un
          Brand DNA estructurado que revisas antes de publicar.
        </p>
      </motion.div>

      <form onSubmit={handleSubmit((values) => void onSubmit(values))} noValidate>
        <motion.div
          variants={surfaceGroup}
          initial="hidden"
          animate="show"
          className="flex flex-col gap-4.5"
        >
          {/* 1. Brand Basics */}
          <SectionCard step={1} title="Brand Basics" description="Lo esencial de la marca.">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="brand_name" className="mb-1.5">
                  Nombre de marca
                </Label>
                <Input id="brand_name" {...register('basics.brand_name')} placeholder="p. ej. Kinu" />
                <FieldErrorText error={errors.basics?.brand_name} />
              </div>
              <div>
                <Label htmlFor="offering" className="mb-1.5">
                  Producto / Oferta
                </Label>
                <Input
                  id="offering"
                  {...register('basics.offering')}
                  placeholder="p. ej. Snack saludable de quinua"
                />
                <FieldErrorText error={errors.basics?.offering} />
              </div>
            </div>
            <div>
              <Label htmlFor="basics_description" className="mb-1.5">
                Descripción de marca <span className="font-normal text-ink-soft">(opcional)</span>
              </Label>
              <Textarea
                id="basics_description"
                rows={2}
                {...register('basics.description')}
                placeholder="Una descripción breve de la marca…"
              />
              <FieldErrorText error={errors.basics?.description} />
            </div>
          </SectionCard>

          {/* 2. Audience */}
          <SectionCard step={2} title="Audience" description="A quién le habla la marca.">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="primary_audience" className="mb-1.5">
                  Audiencia primaria
                </Label>
                <Input
                  id="primary_audience"
                  {...register('audience.primary_audience')}
                  placeholder="p. ej. Gen Z"
                />
                <FieldErrorText error={errors.audience?.primary_audience} />
              </div>
              <div>
                <Label htmlFor="market" className="mb-1.5">
                  Mercado
                </Label>
                <Input id="market" {...register('audience.market')} placeholder="p. ej. Perú" />
                <FieldErrorText error={errors.audience?.market} />
              </div>
            </div>
            <div>
              <Label htmlFor="audience_description" className="mb-1.5">
                Descripción de audiencia
              </Label>
              <Textarea
                id="audience_description"
                rows={2}
                {...register('audience.description')}
                placeholder="Jóvenes que buscan alternativas más saludables y prácticas…"
              />
              <FieldErrorText error={errors.audience?.description} />
            </div>
            <ChipListField
              name="audience.tags"
              label="Tags de audiencia"
              hint="0–10, opcional"
              max={10}
              maxItemLength={60}
              placeholder="p. ej. Wellness"
              getValues={getValues}
              setValue={setValue}
              error={errors.audience?.tags?.root as FieldError | undefined}
            />
          </SectionCard>

          {/* 3. Personality & Tone */}
          <SectionCard
            step={3}
            title="Personality & Tone"
            description="Cómo suena y se comporta la marca."
          >
            <ChipListField
              name="personality.traits"
              label="Rasgos de personalidad y tono"
              hint="1–10 etiquetas"
              max={10}
              maxItemLength={60}
              placeholder="Agregar un tono personalizado…"
              presets={TONE_PRESETS}
              getValues={getValues}
              setValue={setValue}
              error={errors.personality?.traits?.root as FieldError | undefined}
            />
          </SectionCard>

          {/* 4. Brand Rules */}
          <SectionCard
            step={4}
            title="Brand Rules"
            description="Lo que la marca siempre y nunca hace."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <RuleListEditor
                name="rules.always"
                label="ALWAYS"
                min={1}
                max={20}
                placeholder="p. ej. Usa oraciones cortas y enérgicas"
                addLabel="Agregar regla"
                register={register}
                getValues={getValues}
                setValue={setValue}
                rowError={(index) => errors.rules?.always?.[index]}
                rootError={errors.rules?.always?.root}
              />
              <RuleListEditor
                name="rules.never"
                label="NEVER"
                min={1}
                max={20}
                placeholder="p. ej. Usar terminología técnica"
                addLabel="Agregar regla"
                register={register}
                getValues={getValues}
                setValue={setValue}
                rowError={(index) => errors.rules?.never?.[index]}
                rootError={errors.rules?.never?.root}
              />
            </div>
          </SectionCard>
        </motion.div>

        <AnimatePresence>
          {serverError && (
            <motion.p
              key="generate-server-error"
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
            La IA transformará este brief en un Brand DNA estructurado que puedes revisar antes
            de publicar.
          </p>
          <div className="flex gap-2.5">
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => navigate('/brand-dna')}
              className="px-4.5 text-[13.5px]"
            >
              Cancelar
            </Button>
            <Button type="submit" size="lg" disabled={generateBrandDna.isPending}>
              {generateBrandDna.isPending ? 'Generando…' : 'Generate Brand DNA'}
            </Button>
          </div>
        </div>
      </form>
    </motion.div>
  )
}
