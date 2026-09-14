import { ApiError } from '../../shared/api/client'

/** Mensaje presentable para los envelopes de error de las decisiones de review. */
export function describeReviewError(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
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
