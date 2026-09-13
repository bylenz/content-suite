import { useApiHealth } from '../health/useApiHealth'
import { ROLE_PROFILES } from '../session/roles'
import { useSession } from '../session/useSession'
import { EmptyState } from '../../shared/components/StateViews'
import { apiHostLabel } from '../../shared/api/client'

const ONBOARD_STEPS = [
  { n: '01', label: 'Define tu marca' },
  { n: '02', label: 'Genera tu Brand DNA' },
  { n: '03', label: 'Sincroniza el AI Knowledge' },
  { n: '04', label: 'Empieza a crear' },
] as const

const HEALTH_VIEW = {
  ready: {
    dot: 'bg-success-fg',
    pill: 'bg-success-bg text-success-fg',
    label: 'En línea',
    headline: 'API disponible',
  },
  offline: {
    dot: 'bg-strawberry',
    pill: 'bg-danger-bg text-danger-fg',
    label: 'Sin conexión',
    headline: 'API no disponible',
  },
  checking: {
    dot: 'bg-steel animate-pulse-soft',
    pill: 'bg-info-bg text-info-fg',
    label: 'Verificando',
    headline: 'Comprobando la API',
  },
} as const

export function DashboardPage() {
  const { demoRole } = useSession()
  const health = useApiHealth()
  const profile = ROLE_PROFILES[demoRole]
  const view = HEALTH_VIEW[health.state]

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <p className="text-[13px] font-semibold text-ink-soft">Hola, {profile.demoName}</p>
        <h1 className="text-2xl font-bold tracking-tight text-ink">
          {profile.label} · Foundation
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          La base del workspace está lista. Las capacidades de marca se habilitan en
          próximas changes.
        </p>
      </header>

      <div className="grid gap-4.5 lg:grid-cols-[1.1fr_1fr]">
        {/* Panel profundo: estado de la plataforma */}
        <section
          aria-live="polite"
          className="clay clay-deep flex flex-col gap-3.5 p-6 text-white"
        >
          <p className="text-[11px] font-bold uppercase tracking-[0.05em] text-frosted">
            Estado de la plataforma
          </p>
          <div className="flex items-baseline gap-2.5">
            <span className={`size-2.5 self-center rounded-full ${view.dot}`} aria-hidden="true" />
            <span className="text-[34px] font-extrabold leading-none tracking-tight">
              {view.label}
            </span>
          </div>
          <ul className="flex flex-col gap-1.5 text-[13px] text-frosted">
            <li>{view.headline}</li>
            <li>{health.detail}</li>
            <li>
              {health.checkedAt
                ? `Última verificación: ${health.checkedAt.toLocaleTimeString('es')}`
                : 'Sin verificación completada aún'}
            </li>
          </ul>
          {health.state === 'offline' && (
            <button
              type="button"
              onClick={() => void health.refetch()}
              className="clay clay-cta mt-1 w-fit px-5 py-2.5 text-sm font-semibold"
            >
              Reintentar conexión
            </button>
          )}
        </section>

        {/* Tarjeta blanca: detalle de conexión */}
        <section className="clay clay-card flex flex-col gap-3.5 p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="eyebrow">Conexión con la API</h2>
            <span
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11.5px] font-semibold ${view.pill}`}
            >
              <span className={`size-1.5 rounded-full ${view.dot}`} aria-hidden="true" />
              {view.label}
            </span>
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
          <p className="clay clay-subtle px-4 py-3 text-[12.5px] leading-relaxed text-ink-muted">
            El estado se refresca automáticamente cada 15 segundos. La API no invoca
            proveedores AI en sus checks de salud.
          </p>
        </section>
      </div>

      {/* Estado vacío: sin capacidades de marca todavía */}
      <EmptyState
        title="Construye la fuente de verdad de tu marca"
        description="Aún no hay contenido de marca en este workspace. Brand DNA, Creative Studio y las revisiones se habilitarán con sus changes de OpenSpec."
      >
        <ol className="grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {ONBOARD_STEPS.map((step) => (
            <li key={step.n} className="clay clay-chip px-4 py-4 text-left">
              <span className="text-[11px] font-bold tracking-wide text-frosted">
                {step.n}
              </span>
              <p className="mt-2 text-[13px] font-semibold leading-snug text-ink">
                {step.label}
              </p>
            </li>
          ))}
        </ol>
      </EmptyState>
    </div>
  )
}
