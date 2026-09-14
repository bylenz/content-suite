import type { BrandDnaDocument, SectionKey } from '../../shared/api/types'

/** Metadatos de las cinco secciones operativas del documento. */
export const SECTIONS: {
  key: SectionKey
  label: string
  description: string
}[] = [
  {
    key: 'identity',
    label: 'Identidad',
    description: 'Propósito, posicionamiento, personalidad y audiencia.',
  },
  {
    key: 'voice',
    label: 'Voz',
    description: 'Tono, guía de uso, vocabulario preferido/evitado y ejemplos.',
  },
  {
    key: 'communication',
    label: 'Comunicación',
    description: 'Pilares de mensaje y reglas ALWAYS.',
  },
  {
    key: 'visual_rules',
    label: 'Reglas visuales',
    description: 'Personalidad visual, dirección de imagen, composición y logo.',
  },
  {
    key: 'restrictions',
    label: 'Restricciones',
    description: 'Reglas NEVER prohibitivas.',
  },
]

export const SECTION_LABELS: Record<SectionKey, string> = Object.fromEntries(
  SECTIONS.map((section) => [section.key, section.label]),
) as Record<SectionKey, string>

/** Rótulo editorial por sección (vista del documento operativo). */
export function sectionTitle(section: SectionKey): string {
  switch (section) {
    case 'identity':
      return 'Núcleo de marca'
    case 'voice':
      return 'Tono de voz'
    case 'communication':
      return 'Mensajes y reglas'
    case 'visual_rules':
      return 'Guías visuales'
    case 'restrictions':
      return 'Restricciones'
  }
}

/** Etiquetas de campo para la vista y el editor de cada sección. */
export const FIELD_LABELS = {
  identity: {
    purpose: 'Propósito',
    positioning: 'Posicionamiento',
    personality_traits: 'Personalidad',
    audience: 'Audiencia',
  },
  voice: {
    tone_characteristics: 'Características del tono',
    usage_guide: 'Guía de uso',
    preferred_vocabulary: 'Vocabulario preferido',
    avoid_vocabulary: 'Vocabulario a evitar',
    do_examples: 'Ejemplos: hacer',
    dont_examples: 'Ejemplos: no hacer',
  },
  communication: {
    message_pillars: 'Pilares de mensaje',
    rules: 'Reglas ALWAYS',
  },
  visual_rules: {
    visual_personality: 'Personalidad visual',
    imagery_direction: 'Dirección de imagen',
    composition: 'Composición',
    logo_usage: 'Uso del logo',
  },
  restrictions: {
    rules: 'Reglas NEVER',
  },
} as const

/** Límites del contrato, para rótulos de ayuda del editor. */
export const FIELD_LIMITS = {
  narrative: '1–500 caracteres',
  guide: '1–1000 caracteres',
  label: '1–60 caracteres por etiqueta',
  example: '1–300 caracteres por ejemplo',
  rule: '1–300 caracteres por regla',
  pillarName: '1–80 caracteres',
} as const

export type DocumentOfSection = BrandDnaDocument[SectionKey]
