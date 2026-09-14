/**
 * DTOs espejo del módulo visual_audit (`apps/api/app/visual_audit/schemas.py`).
 * Reutiliza `ItemSummary` de Creative (el reviewer decide sobre datos de
 * Creative, no los duplica) y `ConsistencyCheck`/`ConsistencyFinding` de
 * Creative: el backend reutiliza el mismo contrato compartido
 * `app.ai.contracts.Check`/`Finding` para consistency checks y visual audits
 * (severidad `low|medium|high`, estado `pass|fail`).
 */

import type { ConsistencyCheck, ConsistencyFinding, ItemSummary } from '../creative/types'

export type VisualReviewDecision = 'APPROVED' | 'CHANGES_REQUESTED'

export interface VisualAssetOut {
  id: string
  creative_item_id: string
  version: number
  /** Signed URL de corta duración; nunca un path interno de storage (D4). */
  signed_url: string
  metadata: Record<string, unknown>
  uploaded_by: string
  created_at: string
}

export interface VisualAssetList {
  assets: VisualAssetOut[]
}

export interface VisualAuditOut {
  id: string
  visual_asset_id: string
  brand_dna_version_id: string
  checks: ConsistencyCheck[]
  findings: ConsistencyFinding[]
  score: number
  summary: string
  applied_context: Record<string, unknown>
  langfuse_trace_id: string | null
  created_at: string
}

export interface VisualReviewEvidence {
  high_findings: { rule_id: string; category: string; severity: string }[]
}

export interface VisualReviewOut {
  id: string
  visual_audit_id: string
  reviewer_id: string
  decision: VisualReviewDecision
  feedback: string | null
  exception_accepted: boolean
  evidence: VisualReviewEvidence | null
  created_at: string
}

export interface QueueItemOut {
  item: ItemSummary
  asset: VisualAssetOut
  latest_audit: VisualAuditOut | null
}

export interface QueueOut {
  items: QueueItemOut[]
}

export interface DecisionOut {
  item: ItemSummary
  review: VisualReviewOut
}

export interface VisualHistoryEntryOut {
  asset: VisualAssetOut
  audits: VisualAuditOut[]
  reviews: VisualReviewOut[]
}

export interface VisualAuditHistoryOut {
  item: ItemSummary
  entries: VisualHistoryEntryOut[]
}
