import type { BadgeVariant } from '@/components/ui/badge'
import { ApiError } from '../../shared/api/client'
import type { ConsistencyFinding } from '../creative/types'

/** Presentación de severidad de findings (contrato compartido low|medium|high). */
export const SEVERITY_VIEW: Record<ConsistencyFinding['severity'], { label: string; badge: BadgeVariant }> = {
  high: { label: 'HIGH', badge: 'danger' },
  medium: { label: 'MEDIUM', badge: 'warning' },
  low: { label: 'LOW', badge: 'neutral' },
}

export function highFailFindings(findings: ConsistencyFinding[]): ConsistencyFinding[] {
  return findings.filter((f) => f.severity === 'high' && f.status === 'fail')
}

export function failedFindings(findings: ConsistencyFinding[]): ConsistencyFinding[] {
  return findings.filter((f) => f.status === 'fail')
}

export function scoreBadge(score: number): BadgeVariant {
  if (score >= 90) return 'success'
  if (score >= 70) return 'warning'
  return 'danger'
}

/**
 * Mensaje presentable para los envelopes de error de Brand Audit. 503
 * STORAGE_UNAVAILABLE / VISION_OUTPUT_INVALID / KNOWLEDGE_NOT_AVAILABLE son
 * los fail-safe de la spec: estado claro, sin CTA inventada.
 */
export function describeVisualError(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'STORAGE_UNAVAILABLE':
        return 'El storage privado no está configurado en este entorno.'
      case 'VISION_OUTPUT_INVALID':
        return 'El modelo de visión devolvió una salida que no cumple el contrato. No se persistió nada; inténtalo de nuevo.'
      case 'KNOWLEDGE_NOT_AVAILABLE':
        return 'Brand Knowledge visual no está disponible para esta marca. Sincroniza Brand Knowledge antes de auditar.'
      case 'SERVICE_UNAVAILABLE':
        return 'El proveedor de Vision no está configurado en este entorno.'
      case 'VALIDATION_ERROR': {
        const reason = error.details?.['reason']
        if (reason === 'unsupported_file_type') {
          return 'El archivo no es una imagen PNG, JPEG o WebP válida.'
        }
        if (reason === 'file_too_large') {
          return 'El archivo excede el tamaño máximo permitido.'
        }
        if (reason === 'empty_file') {
          return 'El archivo está vacío.'
        }
        return `La API rechazó el archivo: ${error.message}`
      }
      case 'INVALID_WORKFLOW_TRANSITION':
        return `Transición inválida: ${error.message}`
      default:
        return error.message
    }
  }
  return error instanceof Error ? error.message : 'Error inesperado.'
}
