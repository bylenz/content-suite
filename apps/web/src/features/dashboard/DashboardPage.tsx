import { useState } from 'react'
import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError, apiHostLabel } from '../../shared/api/client'
import type { BrandRole } from '../../shared/api/types'
import { formatDate } from '../../shared/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { useApiHealth } from '../health/useApiHealth'
import { useActiveBrand } from '../session/useActiveBrand'
import { useSession } from '../session/useSession'
import { useBrandDna } from '../brand-dna/api'
import { SECTIONS, SECTION_LABELS } from '../brand-dna/sections'
import { KNOWLEDGE_STATUS_VIEW } from '../brand-dna/statusView'
import { ACTIVITY_PAGE_SIZE, usePipeline, useActivity } from './api'
import { activityLabel } from './activityView'
import {
  ROLE_PIPELINE_HIGHLIGHT,
  WORKFLOW_STATUS_LABELS,
  WORKFLOW_STATUS_ORDER,
} from './pipelineView'

/** Mensaje honesto de error de API, reutilizado por los widgets de pipeline y actividad. */
function describeApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.code === 'PERMISSION_DENIED') {
    return 'Tu identidad no tiene acceso a esta marca.'
  }
  return error instanceof Error ? error.message : fallback
}

const HEALTH_VIEW = {
  ready: {
    dot: 'bg-success-fg',
    badge: 'success' as const,
    label: 'En línea',
  },
  offline: {
    dot: 'bg-strawberry',
    badge: 'danger' as const,
    label: 'Sin conexión',
  },
  checking: {
    dot: 'bg-steel',
    badge: 'info' as const,
    label: 'Verificando',
  },
} as const

/** Marca de verificación de la checklist del hero (solo hechos derivados). */
function CheckRow({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-[13px] text-frosted">
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--color-honeydew)"
        strokeWidth="2.2"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d="M4 12l5 5L20 6" />
      </svg>
      {children}
    </li>
  )
}

/**
 * Content Pipeline (change 014): desglose real de los 7 estados de
 * `workflow_status`, con cero explícito en los estados vacíos. Cada rol
 * resalta el subconjunto que le importa (`ROLE_PIPELINE_HIGHLIGHT`) sobre el
 * mismo desglose completo — nunca una variante de endpoint por rol.
 */
function PipelineCard({ brandId, role }: { brandId: string; role: BrandRole }) {
  const pipeline = usePipeline(brandId)
  const highlighted = new Set(ROLE_PIPELINE_HIGHLIGHT[role])

  let body: React.ReactNode
  if (pipeline.isPending) {
    body = <p className="text-sm text-ink-muted">Consultando el pipeline de contenido…</p>
  } else if (pipeline.isError) {
    body = (
      <div className="flex flex-col gap-2.5">
        <p className="text-sm text-ink-muted">
          {describeApiError(pipeline.error, 'No se pudo consultar el pipeline.')}
        </p>
        <Button type="button" onClick={() => void pipeline.refetch()} className="w-fit">
          Reintentar
        </Button>
      </div>
    )
  } else if (pipeline.data.total === 0) {
    body = (
      <p className="text-sm leading-relaxed text-ink-muted">
        Todavía no hay creative items en esta marca. En cuanto el Creator cree contenido, su
        estado de flujo aparecerá aquí.
      </p>
    )
  } else {
    const { counts } = pipeline.data
    body = (
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {WORKFLOW_STATUS_ORDER.map((status) => (
          <li
            key={status}
            className={`flex items-center justify-between gap-2 rounded-[8px] px-3 py-2 text-[12.5px] ${
              highlighted.has(status)
                ? 'bg-tint-steel font-semibold text-info-fg'
                : 'text-ink-soft'
            }`}
          >
            <span>{WORKFLOW_STATUS_LABELS[status]}</span>
            <span className="font-bold text-ink">{counts[status]}</span>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-3.5 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Content Pipeline</h2>
        {pipeline.data && <Badge variant="neutral">{pipeline.data.total} items</Badge>}
      </div>
      {body}
    </motion.section>
  )
}

/**
 * Recent Activity (change 014): feed paginado derivado de `workflow_events` +
 * publicaciones de Brand DNA, en orden cronológico descendente. Nunca
 * fabrica un evento: sin datos reales muestra su estado vacío real.
 */
function ActivityCard({ brandId }: { brandId: string }) {
  const [page, setPage] = useState(0)
  const activity = useActivity(brandId, page)

  let body: React.ReactNode
  if (activity.isPending) {
    body = <p className="text-sm text-ink-muted">Consultando la actividad reciente…</p>
  } else if (activity.isError) {
    body = (
      <div className="flex flex-col gap-2.5">
        <p className="text-sm text-ink-muted">
          {describeApiError(activity.error, 'No se pudo consultar la actividad.')}
        </p>
        <Button type="button" onClick={() => void activity.refetch()} className="w-fit">
          Reintentar
        </Button>
      </div>
    )
  } else if (activity.data.items.length === 0) {
    body = (
      <p className="text-sm leading-relaxed text-ink-muted">
        Todavía no hay actividad registrada en esta marca. Las decisiones de revisión y las
        publicaciones de Brand DNA aparecerán aquí en cuanto ocurran.
      </p>
    )
  } else {
    const { items, total } = activity.data
    const hasPrev = page > 0
    const hasNext = (page + 1) * ACTIVITY_PAGE_SIZE < total
    body = (
      <>
        <ul className="flex flex-col gap-2" aria-label="Actividad reciente">
          {items.map((event) => (
            <li key={event.id} className="clay clay-subtle px-3.5 py-2.5 text-[12.5px]">
              <p className="font-semibold text-ink">{activityLabel(event)}</p>
              <p className="mt-0.5 text-[11px] text-ink-soft">{formatDate(event.created_at)}</p>
            </li>
          ))}
        </ul>
        {total > ACTIVITY_PAGE_SIZE && (
          <nav
            aria-label="Paginación de actividad"
            className="flex items-center justify-between px-0.5"
          >
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!hasPrev}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              ← Anterior
            </Button>
            <p className="text-[11px] font-semibold text-ink-soft">
              Página {page + 1} de {Math.ceil(total / ACTIVITY_PAGE_SIZE)}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!hasNext}
              onClick={() => setPage((current) => current + 1)}
            >
              Siguiente →
            </Button>
          </nav>
        )}
      </>
    )
  }

  return (
    <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-3.5 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Actividad reciente</h2>
        {activity.data && <Badge variant="neutral">{activity.data.total}</Badge>}
      </div>
      {body}
    </motion.section>
  )
}

/**
 * Dashboard API-backed con la composición de la referencia: sidebar elevada
 * (shell), hero azul profundo de estado de marca, tarjetas clay blancas con
 * datos reales del Brand DNA, Content Pipeline y Recent Activity (change 014),
 * y salud de la API. Entrada de superficie con Motion: opacidad + desplazamiento
 * mínimo, escalonado 50 ms y < 300 ms; reduced motion elimina el desplazamiento.
 */
export function DashboardPage() {
  const brand = useActiveBrand()
  const { profile } = useSession()
  const health = useApiHealth()
  const dna = useBrandDna(brand?.brandId ?? '')
  const isCreator = brand?.role === 'CREATOR'
  const healthView = HEALTH_VIEW[health.state]

  const active = dna.data?.active ?? null
  const knowledge = active ? KNOWLEDGE_STATUS_VIEW[active.knowledge_status] : null
  const allSectionsFilled =
    active !== null && SECTIONS.every((section) => (active.section_counts[section.key] ?? 0) > 0)

  return (
    <motion.div
      variants={surfaceGroup}
      initial="hidden"
      animate="show"
      className="flex flex-col gap-5"
    >
      <motion.header variants={surfaceItem} className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1">
          <p className="text-[13px] font-semibold text-ink-soft">
            {profile?.displayName ? `Hola, ${profile.displayName}` : 'Hola'}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            {brand ? `${brand.brandName} Workspace` : 'Workspace'}
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Mantén tu marca consistente en cada pieza de contenido.
          </p>
        </div>
        {/* CTA del encabezado: real cuando el Creator aún no publica; la
            generación de contenido llega con Creative Studio (futura). */}
        {isCreator && dna.data && !active && (
          <Button asChild className="w-fit shrink-0">
            <Link to="/brand-dna/create">Crear Brand DNA</Link>
          </Button>
        )}
        {isCreator && active && (
          <span
            aria-disabled="true"
            title="Creative Studio llega en una change futura"
            className="inline-flex w-fit shrink-0 cursor-default items-center gap-2 rounded-[9px] border border-dashed border-steel/40 px-5 py-2.5 text-sm font-semibold text-ink-muted"
          >
            Create content
            <span className="rounded-[5px] bg-tint-steel px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide">
              Próximamente
            </span>
          </span>
        )}
      </motion.header>

      <div className="grid gap-4.5 lg:grid-cols-[1.1fr_1fr]">
        {/* Hero de estado de marca (azul profundo, datos reales) */}
        <motion.section
          variants={surfaceItem}
          aria-live="polite"
          className="clay clay-deep flex flex-col gap-3.5 p-6 text-white"
        >
          <p className="text-[11px] font-bold uppercase tracking-[0.05em] text-frosted">
            Estado de la marca
          </p>

          {dna.isPending && (
            <p className="text-[13px] text-frosted">Consultando el Brand DNA de la marca…</p>
          )}

          {dna.isError && (
            <div className="flex flex-col gap-2.5">
              <p className="text-[13px] text-frosted">
                {dna.error instanceof ApiError && dna.error.code === 'PERMISSION_DENIED'
                  ? 'Tu identidad no tiene acceso a esta marca.'
                  : dna.error instanceof Error
                    ? dna.error.message
                    : 'No se pudo consultar el Brand DNA.'}
              </p>
              <Button type="button" onClick={() => void dna.refetch()} className="w-fit">
                Reintentar
              </Button>
            </div>
          )}

          {active && (
            <>
              <div className="flex items-baseline gap-2.5">
                <p className="text-[40px] font-extrabold leading-none tracking-tight">
                  v{active.version}
                </p>
                <p className="text-[13px] text-frosted">versión activa publicada</p>
              </div>
              <ul className="flex flex-col gap-1.5">
                <CheckRow>Brand DNA publicado</CheckRow>
                <CheckRow>
                  {allSectionsFilled ? '5 secciones con contenido' : 'Secciones incompletas'}
                </CheckRow>
                <CheckRow>Knowledge: {knowledge?.label}</CheckRow>
              </ul>
            </>
          )}

          {dna.data && !active && isCreator && (
            <div className="flex flex-col gap-3">
              <p className="text-[20px] font-bold leading-tight">Construye la fuente de verdad</p>
              <p className="text-[13px] leading-relaxed text-frosted">
                Aún no hay Brand DNA publicado. Crea el documento que definirá la
                versión activa de tu marca.
              </p>
              <Button asChild className="w-fit">
                <Link to="/brand-dna/create">Crear Brand DNA</Link>
              </Button>
            </div>
          )}
          {dna.data && !active && !isCreator && (
            <p className="text-[13px] leading-relaxed text-frosted">
              Esta marca todavía no ha publicado su Brand DNA. Cuando el Creator lo
              publique lo verás aquí en modo lectura.
            </p>
          )}
        </motion.section>

        {/* Tarjeta clay blanca de Brand DNA */}
        <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-3.5 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="eyebrow">Brand DNA</h2>
            {active ? (
              <Badge variant="deep">
                <span className="size-1.5 rounded-full bg-deep" aria-hidden="true" />
                Activa · v{active.version}
              </Badge>
            ) : (
              !dna.isPending &&
              !dna.isError && <Badge variant="neutral">Sin publicar</Badge>
            )}
          </div>

          {active && knowledge && (
            <>
              <p className="text-[13px] font-semibold text-steel">Knowledge: {knowledge.label}</p>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {SECTIONS.map((section) => (
                  <div key={section.key}>
                    <p className="text-[19px] font-bold text-ink">
                      {active.section_counts[section.key]}
                    </p>
                    <p className="text-[11.5px] text-ink-soft">{SECTION_LABELS[section.key]}</p>
                  </div>
                ))}
              </div>
              <Button asChild variant="secondary" className="mt-1 w-full px-4 py-2.5 text-[13px]">
                <Link to="/brand-dna">Ver Brand DNA</Link>
              </Button>
            </>
          )}

          {!active && (
            <p className="text-sm leading-relaxed text-ink-muted">
              {isCreator
                ? 'Publica tu Brand DNA para establecer la versión activa de tu marca. Knowledge llega en un cambio futuro.'
                : 'El Creator de la marca aún no ha iniciado el Brand DNA.'}
            </p>
          )}
        </motion.section>
      </div>

      {/* Content Pipeline + Recent Activity (change 014): datos reales derivados
          de creative_items/workflow_events/brand_dna_versions, sin agregación. */}
      <div className="grid gap-4.5 lg:grid-cols-[1fr_1.15fr]">
        {brand && <PipelineCard brandId={brand.brandId} role={brand.role} />}
        {brand && <ActivityCard brandId={brand.brandId} />}

        {/* Salud de la API (foundation, datos reales) */}
        <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-3.5 p-6 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="eyebrow">Conexión con la API</h2>
            <Badge variant={healthView.badge}>
              <span className={`size-1.5 rounded-full ${healthView.dot}`} aria-hidden="true" />
              {healthView.label}
            </Badge>
          </div>
          <dl className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <div>
              <dt className="text-[11.5px] text-ink-soft">Endpoint</dt>
              <dd className="text-sm font-semibold text-ink">{apiHostLabel()}</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-ink-soft">Ruta de salud</dt>
              <dd className="text-sm font-semibold text-ink">/health/ready</dd>
            </div>
          </dl>
          {health.state === 'offline' && (
            <Button type="button" onClick={() => void health.refetch()} className="w-fit">
              Reintentar conexión
            </Button>
          )}
        </motion.section>
      </div>
    </motion.div>
  )
}
