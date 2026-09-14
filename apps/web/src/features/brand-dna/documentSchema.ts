import { z } from 'zod'

/**
 * Espejo estricto (Zod) del contrato canónico del documento Brand DNA definido
 * en `openspec/changes/002-brand-dna-authoring/design.md` y en Pydantic
 * (`apps/api/app/brand_dna/schemas.py`). Todo string se recorta antes de
 * validar (`.trim()` encadena antes de min/max); un string vacío tras el
 * recorte es inválido; las claves desconocidas se rechazan (`strictObject`).
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

const Label60 = trimmed(1, 60)
const Example300 = trimmed(1, 300)
const Narrative500 = trimmed(1, 500)

function boundedList<T extends z.ZodType>(item: T, min: number, max: number) {
  return z.array(item).min(min, listMinMsg(min)).max(max, listMaxMsg(max))
}

const identitySectionSchema = z.strictObject({
  purpose: Narrative500,
  positioning: Narrative500,
  personality_traits: boundedList(Label60, 1, 8),
  audience: Narrative500,
})

const voiceSectionSchema = z.strictObject({
  tone_characteristics: boundedList(Label60, 1, 8),
  usage_guide: trimmed(1, 1000),
  preferred_vocabulary: z.array(Label60).max(30, listMaxMsg(30)),
  avoid_vocabulary: z.array(Label60).max(30, listMaxMsg(30)),
  do_examples: boundedList(Example300, 1, 10),
  dont_examples: boundedList(Example300, 1, 10),
})

const messagePillarSchema = z.strictObject({
  name: trimmed(1, 80),
  description: Example300,
})

const communicationSectionSchema = z.strictObject({
  message_pillars: boundedList(messagePillarSchema, 1, 5),
  rules: boundedList(Example300, 1, 20),
})

const visualRulesSectionSchema = z.strictObject({
  visual_personality: Narrative500,
  imagery_direction: Narrative500,
  composition: Narrative500,
  logo_usage: Narrative500,
})

const restrictionsSectionSchema = z.strictObject({
  rules: boundedList(Example300, 1, 20),
})

export const brandDnaDocumentSchema = z.strictObject({
  identity: identitySectionSchema,
  voice: voiceSectionSchema,
  communication: communicationSectionSchema,
  visual_rules: visualRulesSectionSchema,
  restrictions: restrictionsSectionSchema,
})

export type BrandDnaDocumentFormValues = z.input<typeof brandDnaDocumentSchema>
export type BrandDnaDocumentValidated = z.output<typeof brandDnaDocumentSchema>

/** Documento vacío para autoría manual: una fila en cada lista obligatoria. */
export function emptyDocumentValues(): BrandDnaDocumentFormValues {
  return {
    identity: { purpose: '', positioning: '', personality_traits: [''], audience: '' },
    voice: {
      tone_characteristics: [''],
      usage_guide: '',
      preferred_vocabulary: [],
      avoid_vocabulary: [],
      do_examples: [''],
      dont_examples: [''],
    },
    communication: {
      message_pillars: [{ name: '', description: '' }],
      rules: [''],
    },
    visual_rules: {
      visual_personality: '',
      imagery_direction: '',
      composition: '',
      logo_usage: '',
    },
    restrictions: { rules: [''] },
  }
}

/** Copia del documento para inicializar el editor sin mutar el estado del server. */
export function documentToFormValues(document: BrandDnaDocumentFormValues): BrandDnaDocumentFormValues {
  return structuredClone(document)
}
