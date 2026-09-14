import type { ApiErrorEnvelope } from './types'

/** Cliente API mínimo. La URL base se configura con VITE_API_URL. */
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Host legible de la API; tolera URLs mal configuradas. */
export function apiHostLabel(): string {
  try {
    return new URL(API_BASE_URL).host
  } catch {
    return API_BASE_URL
  }
}

/**
 * Token bearer de la sesión actual. Lo fija el SessionProvider tras una
 * autenticación exitosa (o lo limpia al volver a anónimo); nunca se registra.
 */
let authToken: string | null = null

export function setApiAuthToken(token: string | null): void {
  authToken = token
}

export class ApiError extends Error {
  readonly status?: number
  /** Código del envelope centralizado (`UNAUTHENTICATED`, `PERMISSION_DENIED`, …) */
  readonly code?: string
  readonly details?: Record<string, unknown>

  constructor(
    message: string,
    status?: number,
    code?: string,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

/** Traduce un cuerpo de error al mensaje del envelope cuando existe. */
async function toApiError(response: Response): Promise<ApiError> {
  const fallback = new ApiError(`La API respondió ${response.status}`, response.status)
  try {
    const body = (await response.json()) as Partial<ApiErrorEnvelope>
    const error = body?.error
    if (error && typeof error.message === 'string') {
      return new ApiError(error.message, response.status, error.code, error.details)
    }
  } catch {
    // Cuerpo no JSON: se usa el fallback
  }
  return fallback
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers({ Accept: 'application/json', ...init?.headers })
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : 'No se pudo conectar con la API',
    )
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  return (await response.json()) as T
}
