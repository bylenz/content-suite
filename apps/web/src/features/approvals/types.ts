/**
 * DTOs espejo del módulo governance (`apps/api/app/governance/schemas.py`).
 * Reutiliza las formas de Creative (`ItemSummary`, `VersionOut`,
 * `VersionSummary`, `AppliedContextOut`) tal como el backend reutiliza sus
 * schemas: governance decide sobre datos de Creative, no los duplica.
 */

import type { AppliedContextOut, ItemSummary, VersionOut, VersionSummary } from '../creative/types'

export type ContentReviewDecision = 'APPROVED' | 'CHANGES_REQUESTED'

export interface QueueItemOut {
  item: ItemSummary
  submitted_version: VersionSummary
  submitted_at: string
}

export interface QueueOut {
  items: QueueItemOut[]
}

export interface ReviewOut {
  id: string
  creative_item_id: string
  submitted_version_id: string
  reviewer_id: string
  decision: ContentReviewDecision
  feedback: string | null
  created_at: string
}

export interface ReviewDetailOut {
  item: ItemSummary
  submitted_version: VersionOut | null
  applied_context: AppliedContextOut | null
  latest_review: ReviewOut | null
}

export interface WorkflowEventOut {
  id: string
  creative_item_id: string
  event_type: string
  actor_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface ReviewHistoryOut {
  events: WorkflowEventOut[]
}

export interface DecisionOut {
  item: ItemSummary
  review: ReviewOut
}
