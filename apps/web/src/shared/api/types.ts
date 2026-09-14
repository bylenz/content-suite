/**
 * DTOs espejo de la API (`apps/api`). El contrato canónico del documento vive
 * además como esquema Zod estricto en `features/brand-dna/documentSchema.ts`.
 */

export type BrandRole = 'CREATOR' | 'CONTENT_REVIEWER' | 'VISUAL_REVIEWER'

export type BrandDnaStatus = 'DRAFT' | 'ACTIVE' | 'ARCHIVED'

export type KnowledgeStatus = 'NOT_SYNCED' | 'SYNCING' | 'SYNCED' | 'OUTDATED' | 'FAILED'

export interface Membership {
  brand_id: string
  brand_name: string
  brand_slug: string
  role: BrandRole
}

export interface Me {
  id: string
  email: string | null
  display_name: string | null
  memberships: Membership[]
}

export interface IdentitySection {
  purpose: string
  positioning: string
  personality_traits: string[]
  audience: string
}

export interface VoiceSection {
  tone_characteristics: string[]
  usage_guide: string
  preferred_vocabulary: string[]
  avoid_vocabulary: string[]
  do_examples: string[]
  dont_examples: string[]
}

export interface MessagePillar {
  name: string
  description: string
}

export interface CommunicationSection {
  message_pillars: MessagePillar[]
  rules: string[]
}

export interface VisualRulesSection {
  visual_personality: string
  imagery_direction: string
  composition: string
  logo_usage: string
}

export interface RestrictionsSection {
  rules: string[]
}

export interface BrandDnaDocument {
  identity: IdentitySection
  voice: VoiceSection
  communication: CommunicationSection
  visual_rules: VisualRulesSection
  restrictions: RestrictionsSection
}

export type SectionKey = keyof BrandDnaDocument

/** Brief de onboarding que origina una generación (`POST .../generate`). */
export interface BrandBasicsIn {
  brand_name: string
  offering: string
  // La API serializa el campo opcional como `null`, no lo omite.
  description: string | null
}

export interface AudienceIn {
  primary_audience: string
  market: string
  description: string
  tags: string[]
}

export interface PersonalityToneIn {
  traits: string[]
}

export interface BrandRulesIn {
  always: string[]
  never: string[]
}

export interface BrandBriefIn {
  basics: BrandBasicsIn
  audience: AudienceIn
  personality: PersonalityToneIn
  rules: BrandRulesIn
}

export interface BrandDnaVersion {
  id: string
  brand_id: string
  version: number
  status: BrandDnaStatus
  document: BrandDnaDocument
  created_by: string
  created_at: string
  published_at: string | null
  knowledge_status: KnowledgeStatus
  section_counts: Record<SectionKey, number>
  /** El brief que originó la generación (null si nunca se generó por IA). */
  brief: BrandBriefIn | null
}

export interface BrandDnaVersionSummary {
  id: string
  brand_id: string
  version: number
  status: BrandDnaStatus
  created_by: string
  created_at: string
  published_at: string | null
  knowledge_status: KnowledgeStatus
  section_counts: Record<SectionKey, number>
}

export interface BrandDnaOverview {
  active: BrandDnaVersion | null
  draft: BrandDnaVersion | null
}

/** Estado de Knowledge de la versión ACTIVE (`GET .../brand-knowledge/status`). */
export interface KnowledgeStatusOut {
  brand_dna_version_id: string
  version: number
  knowledge_status: KnowledgeStatus
  chunk_count: number | null
  embedding_model: string | null
}

/** Envelope de error centralizado de la API: {error: {code, message, details}}. */
export interface ApiErrorEnvelope {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

/*
 * Observability facade (`GET /api/v1/traces`, change 009). Metadatos
 * allowlist exclusivamente: la facade nunca expone secretos, prompts
 * completos, respuestas crudas ni chain-of-thought.
 */

/** Entidades de dominio enlazables a un trace (design.md 009). */
export type TraceEntityType = 'brand_dna_version' | 'creative_version' | 'visual_audit'

export interface TraceRecord {
  trace_id: string | null
  brand_id: string
  entity_type: TraceEntityType
  entity_id: string | null
  operation: string | null
  prompt_version: string | null
  model: string | null
  latency_ms: number
  outcome: 'ok' | 'error'
  error_type: string | null
  created_at: string
}

export interface TraceListResponse {
  items: TraceRecord[]
  total: number
  /** Estado explícito de Langfuse (spec 07): falso no rompe flujos, solo informa. */
  langfuse_configured: boolean
}
