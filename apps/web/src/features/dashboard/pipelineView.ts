import type { BrandRole, CreativeWorkflowStatus } from '../../shared/api/types'

/** Orden de presentación de los 7 estados reales (DATA_MODEL.md); el backend
 * ya los devuelve completos, este orden es solo de lectura visual. */
export const WORKFLOW_STATUS_ORDER: CreativeWorkflowStatus[] = [
  'DRAFT',
  'PENDING_CONTENT_REVIEW',
  'CONTENT_CHANGES_REQUESTED',
  'CONTENT_APPROVED',
  'PENDING_VISUAL_REVIEW',
  'VISUAL_CHANGES_REQUESTED',
  'FINAL_APPROVED',
]

export const WORKFLOW_STATUS_LABELS: Record<CreativeWorkflowStatus, string> = {
  DRAFT: 'Borrador',
  PENDING_CONTENT_REVIEW: 'Pendiente revisión de contenido',
  CONTENT_CHANGES_REQUESTED: 'Cambios de contenido solicitados',
  CONTENT_APPROVED: 'Contenido aprobado',
  PENDING_VISUAL_REVIEW: 'Pendiente revisión visual',
  VISUAL_CHANGES_REQUESTED: 'Cambios visuales solicitados',
  FINAL_APPROVED: 'Aprobado final',
}

/**
 * Subconjunto que cada rol resalta visualmente sobre el mismo desglose
 * completo de 7 estados (design.md: "el Content Reviewer resalta
 * PENDING_CONTENT_REVIEW"); nunca una variante distinta de endpoint por rol.
 */
export const ROLE_PIPELINE_HIGHLIGHT: Record<BrandRole, CreativeWorkflowStatus[]> = {
  CREATOR: ['DRAFT', 'CONTENT_CHANGES_REQUESTED', 'VISUAL_CHANGES_REQUESTED'],
  CONTENT_REVIEWER: ['PENDING_CONTENT_REVIEW'],
  VISUAL_REVIEWER: ['PENDING_VISUAL_REVIEW'],
}

/** Tono semántico de cada estado (tiles clay del dashboard). Deriva del
 * significado del estado, no del rol: pendientes en ámbar, cambios
 * solicitados en strawberry, aprobados en verde, borrador en steel. */
export type PipelineTone = 'info' | 'warning' | 'danger' | 'success'

export const WORKFLOW_STATUS_TONE: Record<CreativeWorkflowStatus, PipelineTone> = {
  DRAFT: 'info',
  PENDING_CONTENT_REVIEW: 'warning',
  CONTENT_CHANGES_REQUESTED: 'danger',
  CONTENT_APPROVED: 'success',
  PENDING_VISUAL_REVIEW: 'warning',
  VISUAL_CHANGES_REQUESTED: 'danger',
  FINAL_APPROVED: 'success',
}
