import { useState } from 'react'
import { ApiError } from '../../shared/api/client'
import type { TraceRecord } from '../../shared/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PermissionState,
} from '../../shared/components/StateViews'
import { formatDate } from '../../shared/format'
import { useActiveBrand } from '../session/useActiveBrand'
import { TRACES_PAGE_SIZE, toDateIso, useTrace, useTraces } from './api'
import { ENTITY_TYPE_LABELS, formatLatency, OUTCOME_VIEW, shortId } from './tracesView'

/**
 * Fila de trace: solo metadatos allowlist (operación/capability, prompt
 * version, modelo, entidad, latencia, outcome, timestamp). Dato denso:
 * relieve tenue (`clay-subtle`) por legibilidad, no clay completo.
 */
function TraceRow({ trace, onInspect }: { trace: TraceRecord; onInspect: (id: string) => void }) {
  const outcome = OUTCOME_VIEW[trace.outcome]
  return (
    <li>
      <div className="clay clay-subtle clay-hover-raise flex flex-wrap items-center justify-between gap-3 px-4.5 py-3.5">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-[13.5px] font-semibold text-ink">
            {trace.operation ?? trace.prompt_version ?? 'Trace'}
            <Badge variant={outcome.badge} size="sm">
              {outcome.label}
            </Badge>
            <span className="font-mono text-[10.5px] font-semibold text-ink-soft">
              {trace.trace_id ? shortId(trace.trace_id) : 'sin trace id'}
            </span>
          </p>
          <p className="mt-1 flex flex-wrap gap-x-3.5 gap-y-1 text-[11.5px] text-ink-soft">
            <span>
              <span className="font-semibold">Entidad:</span> {ENTITY_TYPE_LABELS[trace.entity_type]}
              {trace.entity_id ? ` · ${shortId(trace.entity_id)}` : ''}
            </span>
            {trace.model && (
              <span>
                <span className="font-semibold">Modelo:</span> {trace.model}
              </span>
            )}
            {trace.prompt_version && (
              <span>
                <span className="font-semibold">Prompt:</span> {trace.prompt_version}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-[12.5px] font-bold text-ink">{formatLatency(trace.latency_ms)}</p>
            <p className="mt-0.5 text-[10.5px] text-ink-soft">{formatDate(trace.created_at)}</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="px-3.5 text-steel"
            onClick={() => trace.trace_id && onInspect(trace.trace_id)}
            disabled={!trace.trace_id}
            title={
              trace.trace_id
                ? 'Ver detalle sanitizado'
                : 'Emitido con tracer no-op: sin trace id de Langfuse no hay detalle disponible'
            }
          >
            Ver detalle
          </Button>
        </div>
      </div>
    </li>
  )
}

/**
 * Detalle sanitizado: exclusivamente los campos allowlist de `TraceRecord`
 * (spec 07). La telemetría profunda (timeline, spans anidados) vive en
 * Langfuse; esta vista nunca la sustituye ni muestra payloads crudos.
 */
function TraceDetail({ traceId, onBack }: { traceId: string; onBack: () => void }) {
  const detail = useTrace(traceId)

  if (detail.isPending) {
    return <LoadingState label="Cargando detalle del trace…" />
  }
  if (detail.isError) {
    const error = detail.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return (
        <div className="flex flex-col gap-4">
          <Button type="button" variant="ghost" size="sm" className="self-start" onClick={onBack}>
            ← Volver al explorador
          </Button>
          <PermissionState title="No tienes acceso a este trace" />
        </div>
      )
    }
    return (
      <div className="flex flex-col gap-4">
        <Button type="button" variant="ghost" size="sm" className="self-start" onClick={onBack}>
          ← Volver al explorador
        </Button>
        <ErrorState
          title="No se pudo cargar el trace"
          description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
          onRetry={() => void detail.refetch()}
        />
      </div>
    )
  }

  const trace = detail.data
  const outcome = OUTCOME_VIEW[trace.outcome]
  return (
    <div className="flex flex-col gap-5">
      <Button type="button" variant="ghost" size="sm" className="self-start" onClick={onBack}>
        ← Volver al explorador
      </Button>
      <header>
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-xl font-bold tracking-tight text-ink">Detalle del trace</h2>
          <Badge variant={outcome.badge}>{outcome.label}</Badge>
        </div>
        <p className="mt-1 font-mono text-[12px] font-semibold text-ink-soft">
          {trace.trace_id ?? 'sin trace id'}
        </p>
      </header>

      {trace.outcome === 'error' && (
        <p
          role="alert"
          className="clay clay-tile bg-danger-bg px-4 py-3 text-[13px] font-medium text-danger-fg"
        >
          Error sanitizado: {trace.error_type ?? 'desconocido'} (solo el tipo; nunca payloads).
        </p>
      )}

      <dl className="clay clay-card grid grid-cols-1 gap-x-5 gap-y-4 px-5 py-5 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Marca</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{trace.brand_id}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Entidad</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">
            {ENTITY_TYPE_LABELS[trace.entity_type]}
            {trace.entity_id ? ` · ${shortId(trace.entity_id)}` : ''}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Operación</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{trace.operation ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">
            Prompt version
          </dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{trace.prompt_version ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Modelo</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{trace.model ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Latencia</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{formatLatency(trace.latency_ms)}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Outcome</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{outcome.label}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[0.04em] text-ink-soft">Fecha</dt>
          <dd className="mt-1 text-[13px] font-semibold text-ink">{formatDate(trace.created_at)}</dd>
        </div>
      </dl>
    </div>
  )
}

/**
 * Superficie Observability (spec 07 / change 009): explorador de traces de la
 * marca activa con filtros mínimos, paginación y detalle sanitizado. La
 * autorización vive en el backend: esta vista siempre envía la marca de la
 * sesión y jamás inventa actividad.
 */
export function ObservabilityPage() {
  const brand = useActiveBrand()
  const [entityType, setEntityType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(0)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)

  // Todos los hooks antes de cualquier early return (orden incondicional).
  const filters = {
    brandId: brand?.brandId ?? '',
    entityType: entityType || undefined,
    from: toDateIso(dateFrom, false),
    to: toDateIso(dateTo, true),
  }
  const traces = useTraces(filters, page)

  if (selectedTraceId) {
    return <TraceDetail traceId={selectedTraceId} onBack={() => setSelectedTraceId(null)} />
  }

  if (!brand) {
    return <PermissionState title="Sin marca en la sesión" />
  }

  if (traces.isPending) {
    return <LoadingState label="Cargando traces…" />
  }
  if (traces.isError) {
    const error = traces.error
    if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
      return <PermissionState />
    }
    return (
      <ErrorState
        title="No se pudieron cargar los traces"
        description={error instanceof Error ? error.message : 'Error desconocido de la API.'}
        onRetry={() => void traces.refetch()}
      />
    )
  }

  const { items, total, langfuse_configured } = traces.data
  const hasPrev = page > 0
  const hasNext = (page + 1) * TRACES_PAGE_SIZE < total

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">System</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Observability</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Interacciones de IA de {brand.brandName}, con metadatos sanitizados.
          </p>
        </div>
        <Badge variant="neutral">{total} traces</Badge>
      </header>

      {/* Estado explícito sin Langfuse (spec 07): informa, no rompe nada. */}
      {!langfuse_configured && (
        <p
          role="status"
          className="clay clay-tile bg-info-bg px-4 py-3 text-[13px] font-medium text-info-fg"
        >
          Langfuse no está configurado en este entorno: el tracing detallado está deshabilitado.
          Los flujos de dominio funcionan con normalidad y los traces locales se siguen registrando
          (sin trace id de Langfuse).
        </p>
      )}

      {/* Filtros mínimos allowlist; el cambio de filtro reinicia la página. */}
      <div className="clay clay-subtle flex flex-wrap items-end gap-4 px-4.5 py-3.5">
        <label className="flex min-w-[190px] flex-col gap-1.5 text-[11.5px] font-semibold text-ink-soft">
          Tipo de entidad
          <select
            aria-label="Filtrar por tipo de entidad"
            value={entityType}
            onChange={(event) => {
              setEntityType(event.target.value)
              setPage(0)
            }}
            className="clay-field border-0 px-3.5 py-2.5 text-[13.5px] text-ink"
          >
            <option value="">Todas</option>
            {Object.entries(ENTITY_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-[11.5px] font-semibold text-ink-soft">
          Desde
          <Input
            type="date"
            aria-label="Filtrar desde la fecha"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value)
              setPage(0)
            }}
            className="w-[160px]"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-[11.5px] font-semibold text-ink-soft">
          Hasta
          <Input
            type="date"
            aria-label="Filtrar hasta la fecha"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value)
              setPage(0)
            }}
            className="w-[160px]"
          />
        </label>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="Sin traces todavía"
          description="Cuando se ejecuten capabilities de IA (generación, consistencia o auditoría), sus traces sanitizados aparecerán aquí. La telemetría profunda vive en Langfuse; esta vista nunca la sustituye."
        />
      ) : (
        <ul className="flex flex-col gap-2.5" aria-label="Lista de traces">
          {items.map((trace, index) => (
            <TraceRow key={trace.trace_id ?? `${trace.entity_type}-${index}`} trace={trace} onInspect={setSelectedTraceId} />
          ))}
        </ul>
      )}

      {total > TRACES_PAGE_SIZE && (
        <nav
          aria-label="Paginación de traces"
          className="flex items-center justify-between px-1"
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="px-3.5 text-steel"
            disabled={!hasPrev}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            ← Anterior
          </Button>
          <p className="text-[12px] font-semibold text-ink-soft">
            Página {page + 1} de {Math.ceil(total / TRACES_PAGE_SIZE)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="px-3.5 text-steel"
            disabled={!hasNext}
            onClick={() => setPage((current) => current + 1)}
          >
            Siguiente →
          </Button>
        </nav>
      )}
    </div>
  )
}
