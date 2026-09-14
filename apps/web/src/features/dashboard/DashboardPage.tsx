import { Link } from 'react-router'
import { motion } from 'motion/react'
import { ApiError, apiHostLabel } from '../../shared/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { surfaceGroup, surfaceItem } from '../../shared/motion'
import { useApiHealth } from '../health/useApiHealth'
import { useActiveBrand } from '../session/useActiveBrand'
import { useSession } from '../session/useSession'
import { useBrandDna } from '../brand-dna/api'
import { SECTIONS, SECTION_LABELS } from '../brand-dna/sections'
import { KNOWLEDGE_STATUS_VIEW } from '../brand-dna/statusView'

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
 * Placeholder honesto de capacidades futuras: nunca muestra métricas ni
 * eventos que puedan parecer datos reales y no es interactivo.
 */
function FutureCard({ title, description }: { title: string; description: string }) {
  return (
    <motion.section
      variants={surfaceItem}
      aria-disabled="true"
      className="clay clay-card flex flex-col gap-3 border border-dashed border-steel/30 p-6"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">{title}</h2>
        <span className="rounded-[6px] bg-tint-steel px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-info-fg">
          Próximamente
        </span>
      </div>
      <p className="text-sm leading-relaxed text-ink-muted">{description}</p>
    </motion.section>
  )
}

/**
 * Dashboard API-backed con la composición de la referencia: sidebar elevada
 * (shell), hero azul profundo de estado de marca, tarjetas clay blancas con
 * datos reales del Brand DNA y salud de la API. Los widgets sin contrato
 * backend (pipeline, actividad) permanecen placeholders no interactivos.
 * Entrada de superficie con Motion: opacidad + desplazamiento mínimo,
 * escalonado 50 ms y < 300 ms; reduced motion elimina el desplazamiento.
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
                ? 'Publica tu Brand DNA para establecer la versión activa de tu marca. Knowledge y Content Pipeline llegan en cambios futuros.'
                : 'El Creator de la marca aún no ha iniciado el Brand DNA.'}
            </p>
          )}
        </motion.section>
      </div>

      {/* Widgets sin contrato backend: placeholders futuros no interactivos */}
      <div className="grid gap-4.5 lg:grid-cols-[1fr_1.15fr]">
        <FutureCard
          title="Content Pipeline"
          description="El flujo de piezas de contenido llega con Creative Studio."
        />
        <FutureCard
          title="Actividad reciente"
          description="El registro de actividad del equipo llega con Governance."
        />

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
