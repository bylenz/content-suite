import { useQuery } from '@tanstack/react-query'
import { apiFetch, apiHostLabel } from '../../shared/api/client'

export type HealthState = 'checking' | 'ready' | 'offline'

export interface HealthStatus {
  state: HealthState
  /** Mensaje legible para el estado actual */
  detail: string
  checkedAt: Date | null
}

interface ReadyResponse {
  status?: string
}

/**
 * Consulta el estado de salud de la API (`GET /health/ready`).
 * Sin llamadas a proveedores AI; solo disponibilidad del proceso y sus
 * dependencias esenciales según lo que el backend reporte.
 */
export function useApiHealth() {
  const query = useQuery({
    queryKey: ['api-health-ready'],
    queryFn: async () => {
      const data = await apiFetch<ReadyResponse>('/health/ready')
      return { reported: data.status ?? 'ok', checkedAt: new Date() }
    },
    refetchInterval: 15_000,
    retry: 0,
  })

  const state: HealthState = query.isPending
    ? 'checking'
    : query.isError
      ? 'offline'
      : 'ready'

  const detail =
    state === 'checking'
      ? 'Verificando conexión con la API…'
      : state === 'offline'
        ? query.error instanceof Error
          ? query.error.message
          : 'No se pudo alcanzar la API.'
        : `La API responde en ${apiHostLabel()}/health/ready`

  return {
    state,
    detail,
    checkedAt: query.data?.checkedAt ?? null,
    refetch: query.refetch,
  }
}
