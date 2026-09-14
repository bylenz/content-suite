/**
 * DTOs espejo del módulo creative (`apps/api/app/creative/schemas.py` +
 * `ai/contracts.py`). El contrato canónico persistente es `CreativeOutput`;
 * la edición humana reutiliza la misma forma.
 */

export type CreativeItemType = 'PRODUCT_DESCRIPTION' | 'VIDEO_SCRIPT' | 'IMAGE_PROMPT'

export type CreativeContentType = 'product_description' | 'video_script' | 'image_prompt'

export type CreativeVersionOrigin = 'AI_GENERATED' | 'AI_REGENERATED' | 'HUMAN_EDIT'

export type CreativeWorkflowStatus =
  | 'DRAFT'
  | 'PENDING_CONTENT_REVIEW'
  | 'CONTENT_CHANGES_REQUESTED'
  | 'CONTENT_APPROVED'
  | 'PENDING_VISUAL_REVIEW'
  | 'VISUAL_CHANGES_REQUESTED'
  | 'FINAL_APPROVED'

export interface CreativeSection {
  heading: string
  body: string
}

export interface CreativeOutput {
  content_type: CreativeContentType
  title: string
  /** Exactamente uno de content / structured_sections está presente. */
  content: string | null
  structured_sections: CreativeSection[] | null
  applied_rule_ids: string[]
}

export interface ItemSummary {
  id: string
  brand_id: string
  type: CreativeItemType
  title: string
  workflow_status: CreativeWorkflowStatus
  created_by: string
  created_at: string
  updated_at: string
  latest_version: number
}

export interface VersionSummary {
  id: string
  creative_item_id: string
  version: number
  origin: CreativeVersionOrigin
  brand_dna_version_id: string | null
  consistency_score: number | null
  created_by: string
  created_at: string
}

export interface VersionOut extends VersionSummary {
  brief: Record<string, unknown>
  output: CreativeOutput | null
  applied_rule_ids: string[]
  consistency_result: ConsistencyResultPayload | null
  langfuse_trace_id: string | null
}

export interface ItemOut extends ItemSummary {
  current_version: VersionOut | null
}

export interface ItemList {
  items: ItemSummary[]
}

export interface VersionList {
  versions: VersionSummary[]
}

export interface AppliedContextOut {
  creative_item_id: string
  version_id: string
  version: number
  brand_dna_version_id: string | null
  applied_rule_ids: string[]
}

/** ConsistencyResult del contrato AI + trace_id del run (payload persistido). */
export interface ConsistencyResultPayload {
  checks: ConsistencyCheck[]
  findings: ConsistencyFinding[]
  summary: string
  trace_id?: string | null
}

export interface ConsistencyCheck {
  check_id: string
  label: string
  status: 'pass' | 'fail'
}

export interface ConsistencyFinding {
  rule_id: string
  category: string
  expected: string
  detected: string
  evidence: string
  recommendation: string
  severity: 'low' | 'medium' | 'high'
  status: 'pass' | 'fail'
}
