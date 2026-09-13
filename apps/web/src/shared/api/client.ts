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

export class ApiError extends Error {
  readonly status?: number

  constructor(
    message: string,
    status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json', ...init?.headers },
      ...init,
    })
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : 'No se pudo conectar con la API',
    )
  }
  if (!response.ok) {
    throw new ApiError(`La API respondió ${response.status}`, response.status)
  }
  return (await response.json()) as T
}
