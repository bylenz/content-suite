import type { BadgeVariant } from '@/components/ui/badge'
import { ApiError } from '../../shared/api/client'
import type { CreativeItemType, CreativeWorkflowStatus, CreativeVersionOrigin } from './types'

/** Presentación de tipos, orígenes y estados reales del workflow creative. */

export const TYPE_VIEW: Record<CreativeItemType, { label: string; description: string }> = {
  PRODUCT_DESCRIPTION: {
    label: 'Product Description',
    description: 'Texto comercial del producto, con el tono y las reglas del Brand DNA.',
  },
  VIDEO_SCRIPT: {
    label: 'Video Script',
    description: 'Guion por secciones (visual + voz en off) para video corto.',
  },
  IMAGE_PROMPT: {
    label: 'Image Prompt',
    description: 'Prompt final para generar el visual con las reglas visuales de la marca.',
  },
}

export const WORKFLOW_STATUS_VIEW: Record<
  CreativeWorkflowStatus,
  { label: string; badge: BadgeVariant }
> = {
  DRAFT: { label: 'Borrador', badge: 'info' },
  PENDING_CONTENT_REVIEW: { label: 'En revisión de contenido', badge: 'warning' },
  CONTENT_CHANGES_REQUESTED: { label: 'Cambios solicitados', badge: 'danger' },
  CONTENT_APPROVED: { label: 'Contenido aprobado', badge: 'success' },
  PENDING_VISUAL_REVIEW: { label: 'En revisión visual', badge: 'warning' },
  VISUAL_CHANGES_REQUESTED: { label: 'Cambios visuales solicitados', badge: 'danger' },
  FINAL_APPROVED: { label: 'Aprobado final', badge: 'success' },
}

export const ORIGIN_VIEW: Record<CreativeVersionOrigin, { label: string; badge: BadgeVariant }> = {
  AI_GENERATED: { label: 'Generado por IA', badge: 'info' },
  AI_REGENERATED: { label: 'Regenerado por IA', badge: 'info' },
  HUMAN_EDIT: { label: 'Edición humana', badge: 'neutral' },
}

/** Estados donde el Creator puede autorar nuevas versiones (WORKFLOWS.md). */
export const EDITABLE_STATUSES: readonly CreativeWorkflowStatus[] = [
  'DRAFT',
  'CONTENT_CHANGES_REQUESTED',
]

export function isEditable(status: CreativeWorkflowStatus): boolean {
  return EDITABLE_STATUSES.includes(status)
}

/**
 * Mensaje presentable para los envelopes de error de las mutaciones creative.
 * 503 KNOWLEDGE_NOT_AVAILABLE es el fail-safe de la spec: estado claro, sin
 * CTA inventada.
 */
export function describeMutationError(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'KNOWLEDGE_NOT_AVAILABLE':
        return 'Brand Knowledge no está sincronizado para esta marca. Sincroniza desde Brand DNA antes de generar, verificar o enviar.'
      case 'AI_OUTPUT_INVALID':
        return 'El proveedor devolvió una salida que no cumple el contrato estructurado. No se persistió nada; inténtalo de nuevo.'
      case 'SERVICE_UNAVAILABLE':
        return 'El proveedor de IA no está configurado en este entorno.'
      case 'INVALID_WORKFLOW_TRANSITION':
        return `Transición inválida: ${error.message}`
      case 'VALIDATION_ERROR': {
        const fields = error.details?.['field_errors']
        return `La API rechazó el payload: ${
          Array.isArray(fields) ? fields.join(', ') : error.message
        }`
      }
      default:
        return error.message
    }
  }
  return error instanceof Error ? error.message : 'Error inesperado.'
}
