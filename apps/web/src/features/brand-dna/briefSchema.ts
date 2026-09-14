import { z } from 'zod'

/**
 * Espejo estricto (Zod) del `BrandBriefIn` de la API
 * (`apps/api/app/brand_dna/schemas.py`): brief de onboarding que origina una
 * generación asistida por IA del borrador de Brand DNA. Cuatro secciones,
 * acorde a `starter-design/Content Suite.dc.html`: Brand Basics, Audience,
 * Personality & Tone, Brand Rules.
 */

const REQUIRED = 'Este campo es obligatorio'
const maxMsg = (n: number) => `Máximo ${n} caracteres`
const listMinMsg = (n: number) => `Agrega al menos ${n} ${n === 1 ? 'elemento' : 'elementos'}`
const listMaxMsg = (n: number) => `Máximo ${n} elementos`

const trimmed = (min: number, max: number) =>
  z
    .string()
    .trim()
    .min(min, min <= 1 ? `${REQUIRED} (sin espacios en blanco)` : `Mínimo ${min} caracteres`)
    .max(max, maxMsg(max))

const BriefField = trimmed(1, 120)
const Narrative500 = trimmed(1, 500)
const Label60 = trimmed(1, 60)
const Example300 = trimmed(1, 300)

function boundedList<T extends z.ZodType>(item: T, min: number, max: number) {
  return z.array(item).min(min, listMinMsg(min)).max(max, listMaxMsg(max))
}

const basicsSchema = z.strictObject({
  brand_name: BriefField,
  offering: BriefField,
  // Opcional en la API (serializada como `null`, no omitida): un campo vacío
  // en el formulario se envía como `null`.
  description: z
    .string()
    .trim()
    .max(500, maxMsg(500))
    .transform((value) => (value.length === 0 ? null : value)),
})

const audienceSchema = z.strictObject({
  primary_audience: BriefField,
  market: BriefField,
  description: Narrative500,
  tags: z.array(Label60).max(10, listMaxMsg(10)),
})

const personalitySchema = z.strictObject({
  traits: boundedList(Label60, 1, 10),
})

const rulesSchema = z.strictObject({
  always: boundedList(Example300, 1, 20),
  never: boundedList(Example300, 1, 20),
})

export const brandBriefSchema = z.strictObject({
  basics: basicsSchema,
  audience: audienceSchema,
  personality: personalitySchema,
  rules: rulesSchema,
})

export type BrandBriefFormValues = z.input<typeof brandBriefSchema>
export type BrandBriefValidated = z.output<typeof brandBriefSchema>

/** Preajustes del mockup: chips de tono/personalidad sugeridos. */
export const TONE_PRESETS = [
  'Playful',
  'Professional',
  'Energetic',
  'Friendly',
  'Bold',
  'Educational',
] as const

/** Brief vacío para el formulario: listas con una fila para guiar la carga. */
export function emptyBriefValues(): BrandBriefFormValues {
  return {
    basics: { brand_name: '', offering: '', description: '' },
    audience: { primary_audience: '', market: '', description: '', tags: [] },
    personality: { traits: [] },
    rules: { always: [''], never: [''] },
  }
}
