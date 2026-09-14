import { useState } from 'react'
import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError, apiHostLabel } from '../../shared/api/client'
import type { BrandRole, SectionKey } from '../../shared/api/types'
import { formatDate } from '../../shared/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { surfaceGroup, surfaceItem, tileGroup, tileItem } from '../../shared/motion'
import { useApiHealth } from '../health/useApiHealth'
import { useActiveBrand } from '../session/useActiveBrand'
import { useSession } from '../session/useSession'
import { useBrandDna } from '../brand-dna/api'
import { SECTIONS, SECTION_LABELS } from '../brand-dna/sections'
import { KNOWLEDGE_STATUS_VIEW } from '../brand-dna/statusView'
import { ACTIVITY_PAGE_SIZE, usePipeline, useActivity } from './api'
import { activityLabel, activityTone, type ActivityTone } from './activityView'
import {
  ROLE_PIPELINE_HIGHLIGHT,
  WORKFLOW_STATUS_LABELS,
  WORKFLOW_STATUS_ORDER,
  WORKFLOW_STATUS_TONE,
  type PipelineTone,
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
    dot: 'bg-success-solid',
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

/** Clases de fondo/texto/icono por tono semántico (tiles clay). */
const TONE_CLASSES: Record<PipelineTone, { tile: string; icon: string; count: string }> = {
  info: { tile: 'bg-info-bg', icon: 'text-steel', count: 'text-info-fg' },
  warning: { tile: 'bg-warning-bg', icon: 'text-warning-fg', count: 'text-warning-fg' },
  danger: { tile: 'bg-danger-bg', icon: 'text-danger-fg', count: 'text-danger-fg' },
  success: { tile: 'bg-success-bg', icon: 'text-success-fg', count: 'text-success-fg' },
}

const ACTIVITY_DOT: Record<ActivityTone, string> = {
  success: 'bg-success-solid',
  danger: 'bg-strawberry',
  info: 'bg-frosted',
  deep: 'bg-deep',
  neutral: 'bg-steel',
}

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}

/** Glifo de cada estado del pipeline (solo trazos SVG, sin color propio). */
function PipelineIcon({ tone }: { tone: PipelineTone }) {
  switch (tone) {
    case 'info':
      return (
        <svg {...ICON_PROPS}>
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          <path d="M14 3v5h5" />
        </svg>
      )
    case 'warning':
      return (
        <svg {...ICON_PROPS}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      )
    case 'danger':
      return (
        <svg {...ICON_PROPS}>
          <circle cx="12" cy="12" r="9" />
          <path d="M9 9l6 6M15 9l-6 6" />
        </svg>
      )
    case 'success':
      return (
        <svg {...ICON_PROPS}>
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12l3 3 5-6" />
        </svg>
      )
  }
}

/** Glifo de cada sección del Brand DNA (tiles de la tarjeta Brand DNA). */
function SectionIcon({ section }: { section: SectionKey }) {
  switch (section) {
    case 'identity':
      return (
        <svg {...ICON_PROPS}>
          <path d="M12 2 L21 12 L12 22 L3 12 Z" />
        </svg>
      )
    case 'voice':
      return (
        <svg {...ICON_PROPS}>
          <path d="M4 5h16v10H9l-5 4z" />
        </svg>
      )
    case 'communication':
      return (
        <svg {...ICON_PROPS}>
          <path d="M3 10v4l11 4V6z" />
          <path d="M14 9a3 3 0 0 1 0 6M6 14v4" />
        </svg>
      )
    case 'visual_rules':
      return (
        <svg {...ICON_PROPS}>
          <rect x="3" y="4" width="18" height="16" rx="3" />
          <circle cx="9" cy="10" r="1.6" />
          <path d="M21 16l-5-5-8 8" />
        </svg>
      )
    case 'restrictions':
      return (
        <svg {...ICON_PROPS}>
          <circle cx="12" cy="12" r="9" />
          <path d="M6 6l12 12" />
        </svg>
      )
  }
}

/** Marca de verificación de la checklist del hero (solo hechos derivados). */
function CheckRow({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3 text-[13.5px] text-honeydew">
      <span
        aria-hidden="true"
        className="clay-dot grid size-6 shrink-0 place-items-center bg-success-solid text-white"
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M5 12l5 5L20 7" />
        </svg>
      </span>
      {children}
    </li>
  )
}

/**
 * Barras decorativas del hero (estilo clay de la referencia). Puramente
 * ornamentales: no representan datos y quedan fuera del árbol accesible.
 */
function HeroBars() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute bottom-6 right-7 hidden items-end gap-3 sm:flex"
    >
      {[52, 84, 118].map((height, index) => (
        <span
          key={height}
          style={{ height, animationDelay: `${120 + index * 90}ms` }}
          className="animate-rise-bar block w-9 rounded-full bg-[linear-gradient(180deg,rgba(255,255,255,.22),rgba(255,255,255,0)_45%),linear-gradient(180deg,var(--color-steel),var(--color-deep))] shadow-[8px_10px_20px_rgba(0,0,0,.35),-4px_-4px_10px_rgba(255,255,255,.12),inset_0_2px_0_rgba(255,255,255,.35),inset_-3px_-4px_8px_rgba(0,0,0,.3)]"
        />
      ))}
    </div>
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
      <motion.ul
        variants={tileGroup}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2"
      >
        {WORKFLOW_STATUS_ORDER.map((status) => {
          const tone = WORKFLOW_STATUS_TONE[status]
          const classes = TONE_CLASSES[tone]
          const isHighlighted = highlighted.has(status)
          return (
            <motion.li
              key={status}
              variants={tileItem}
              data-highlighted={isHighlighted ? 'true' : undefined}
              className={`clay-tile clay-hover-raise flex items-center justify-between gap-3 px-4 py-3 ${
                classes.tile
              } ${isHighlighted ? '' : 'opacity-80'}`}
            >
              <span className="min-w-0">
                <span className={`block text-[22px] font-extrabold leading-none ${classes.count}`}>
                  {counts[status]}
                </span>
                <span
                  className={`mt-1 block text-[12px] leading-snug ${
                    isHighlighted ? 'font-semibold text-ink' : 'text-ink-muted'
                  }`}
                >
                  {WORKFLOW_STATUS_LABELS[status]}
                </span>
              </span>
              <span className={`clay-icon size-10 shrink-0 ${classes.icon}`}>
                <PipelineIcon tone={tone} />
              </span>
            </motion.li>
          )
        })}
      </motion.ul>
    )
  }

  return (
    <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-4 p-6">
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
        <motion.ul
          key={page}
          variants={tileGroup}
          initial="hidden"
          animate="show"
          className="flex flex-col gap-2.5"
          aria-label="Actividad reciente"
        >
          {items.map((event) => (
            <motion.li
              key={event.id}
              variants={tileItem}
              className="clay clay-subtle clay-hover-raise flex items-center gap-3 px-4 py-3 text-[12.5px]"
            >
              <span
                aria-hidden="true"
                className={`clay-dot size-3.5 shrink-0 ${ACTIVITY_DOT[activityTone(event)]}`}
              />
              <span className="min-w-0">
                <p className="font-semibold text-ink">{activityLabel(event)}</p>
                <p className="mt-0.5 text-[11px] text-ink-soft">{formatDate(event.created_at)}</p>
              </span>
            </motion.li>
          ))}
        </motion.ul>
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
    <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Actividad reciente</h2>
        {activity.data && <Badge variant="neutral">{activity.data.total}</Badge>}
      </div>
      {body}
    </motion.section>
  )
}

/**
 * Dashboard API-backed con la composición de la referencia: sidebar flotante
 * (shell), hero azul profundo de estado de marca con volumen clay, tarjetas
 * blancas elevadas con tiles de dato (Brand DNA, Content Pipeline), Recent
 * Activity (change 014) y salud de la API. Entrada de superficie con Motion:
 * muelle corto + opacidad, escalonado 60 ms; reduced motion elimina el
 * desplazamiento.
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
      className="flex flex-col gap-6"
    >
      <motion.header variants={surfaceItem} className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1">
          <p className="text-[13.5px] font-semibold text-ink-soft">
            {profile?.displayName ? `Hola, ${profile.displayName}` : 'Hola'}
          </p>
          <h1 className="text-[30px] font-extrabold leading-tight tracking-tight text-ink">
            {brand ? `${brand.brandName} Workspace` : 'Workspace'}
          </h1>
          <p className="mt-1 text-[15px] text-ink-muted">
            Mantén tu marca consistente en cada pieza de contenido.
          </p>
        </div>
        {/* CTA del encabezado (solo Creator): sin Brand DNA publicado, el
            primer paso es crearlo; con versión activa, crear contenido en
            Creative Studio. Los revisores no tienen acción de escritura. */}
        {isCreator && dna.data && !active && (
          <Button asChild size="lg" className="w-fit shrink-0">
            <Link to="/brand-dna/create">Crear Brand DNA</Link>
          </Button>
        )}
        {isCreator && active && (
          <Button asChild size="lg" className="w-fit shrink-0">
            <Link to="/creative">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
              Crear contenido
            </Link>
          </Button>
        )}
      </motion.header>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        {/* Hero de estado de marca (azul profundo, datos reales) */}
        <motion.section
          variants={surfaceItem}
          aria-live="polite"
          className="clay clay-deep relative flex flex-col gap-4 overflow-hidden p-7 text-white"
        >
          <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-frosted">
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
              <div className="flex flex-wrap items-baseline gap-3">
                <p className="text-[64px] font-extrabold leading-none tracking-tight drop-shadow-[0_4px_10px_rgba(0,0,0,.3)]">
                  v{active.version}
                </p>
                <p className="text-[13.5px] text-frosted">versión activa publicada</p>
              </div>
              <ul className="flex flex-col gap-2.5">
                <CheckRow>Brand DNA publicado</CheckRow>
                <CheckRow>
                  {allSectionsFilled ? '5 secciones con contenido' : 'Secciones incompletas'}
                </CheckRow>
                <CheckRow>Knowledge: {knowledge?.label}</CheckRow>
              </ul>
              <HeroBars />
            </>
          )}

          {dna.data && !active && isCreator && (
            <div className="flex flex-col gap-3">
              <p className="text-[22px] font-bold leading-tight">Construye la fuente de verdad</p>
              <p className="max-w-[34ch] text-[13.5px] leading-relaxed text-frosted">
                Aún no hay Brand DNA publicado. Crea el documento que definirá la
                versión activa de tu marca.
              </p>
              <Button asChild className="w-fit">
                <Link to="/brand-dna/create">Crear Brand DNA</Link>
              </Button>
              <HeroBars />
            </div>
          )}
          {dna.data && !active && !isCreator && (
            <>
              <p className="max-w-[34ch] text-[13.5px] leading-relaxed text-frosted">
                Esta marca todavía no ha publicado su Brand DNA. Cuando el Creator lo
                publique lo verás aquí en modo lectura.
              </p>
              <HeroBars />
            </>
          )}
        </motion.section>

        {/* Tarjeta clay blanca de Brand DNA */}
        <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-4 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="eyebrow">Brand DNA</h2>
            {active ? (
              <Badge variant="deep">
                <span className="clay-dot size-2 bg-success-solid" aria-hidden="true" />
                Activa · v{active.version}
              </Badge>
            ) : (
              !dna.isPending &&
              !dna.isError && <Badge variant="neutral">Sin publicar</Badge>
            )}
          </div>

          {active && knowledge && (
            <>
              <p className="text-[15px] font-bold text-steel">Knowledge: {knowledge.label}</p>
              <motion.div
                variants={tileGroup}
                initial="hidden"
                animate="show"
                className="grid grid-cols-2 gap-3 [&>:last-child:nth-child(odd)]:col-span-2"
              >
                {SECTIONS.map((section) => (
                  <motion.div
                    key={section.key}
                    variants={tileItem}
                    className="clay-tile clay-hover-raise flex items-center justify-between gap-3 bg-tint-frosted px-4 py-3"
                  >
                    <span className="min-w-0">
                      <span className="block text-[22px] font-extrabold leading-none text-ink">
                        {active.section_counts[section.key]}
                      </span>
                      <span className="mt-1 block text-[12px] text-ink-muted">
                        {SECTION_LABELS[section.key]}
                      </span>
                    </span>
                    <span className="clay-icon size-10 shrink-0 text-steel">
                      <SectionIcon section={section.key} />
                    </span>
                  </motion.div>
                ))}
              </motion.div>
              <Button asChild variant="secondary" className="mt-1 w-full px-4 py-3 text-[14px]">
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
      <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
        {brand && <PipelineCard brandId={brand.brandId} role={brand.role} />}
        {brand && <ActivityCard brandId={brand.brandId} />}

        {/* Salud de la API (foundation, datos reales) */}
        <motion.section variants={surfaceItem} className="clay clay-card flex flex-col gap-4 p-6 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="eyebrow">Conexión con la API</h2>
            <Badge variant={healthView.badge}>
              <span className={`clay-dot size-2 ${healthView.dot}`} aria-hidden="true" />
              {healthView.label}
            </Badge>
          </div>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="clay-tile bg-tint-frosted px-4 py-3">
              <dt className="text-[11.5px] text-ink-soft">Endpoint</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink">{apiHostLabel()}</dd>
            </div>
            <div className="clay-tile bg-tint-frosted px-4 py-3">
              <dt className="text-[11.5px] text-ink-soft">Ruta de salud</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink">/health/ready</dd>
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
