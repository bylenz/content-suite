import type { ReactNode } from 'react'

/**
 * Estados mínimos de la interfaz (carga, vacío, error).
 * Conservan la jerarquía visual del shell y usan estados semánticos legibles.
 */

export function LoadingState({ label }: { label: string }) {
  return (
    <section
      role="status"
      aria-live="polite"
      className="clay clay-card mx-auto flex w-full max-w-xl flex-col items-center gap-4 px-8 py-12 text-center"
    >
      <span
        aria-hidden="true"
        className="animate-pulse-soft size-3 rounded-full bg-steel shadow-[inset_0_1px_0_rgba(255,255,255,.6)]"
      />
      <p className="text-sm font-semibold text-ink">{label}</p>
      <p className="text-xs text-ink-muted">Un momento, por favor.</p>
    </section>
  )
}

export function EmptyState({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <section className="clay clay-card flex flex-col items-center gap-5 px-8 py-10 text-center">
      <span
        aria-hidden="true"
        className="clay clay-chip grid size-14 place-items-center text-steel"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 2 L21 12 L12 22 L3 12 Z" />
        </svg>
      </span>
      <div className="max-w-md">
        <h2 className="text-lg font-bold tracking-tight text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{description}</p>
      </div>
      {children}
    </section>
  )
}

export function ErrorState({
  title,
  description,
  onRetry,
  children,
}: {
  title: string
  description: string
  onRetry?: () => void
  children?: ReactNode
}) {
  return (
    <section
      role="alert"
      className="clay clay-card flex flex-col items-center gap-4 px-8 py-10 text-center"
    >
      <span
        aria-hidden="true"
        className="grid size-10 place-items-center rounded-[10px] bg-danger-bg text-danger-fg"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 9v4M12 17h.01M10.3 3.9 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        </svg>
      </span>
      <div className="max-w-md">
        <h2 className="text-base font-bold text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{description}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="clay clay-cta px-5 py-2.5 text-sm font-semibold transition-transform duration-150 active:translate-y-px"
        >
          Reintentar
        </button>
      )}
      {children}
    </section>
  )
}

/**
 * Vista anónima: el visitante sin sesión no ve el shell. La única entrada
 * disponible es explícita (modo demo de presentación, no autenticación).
 */
export function SessionMissingState({ onEnterDemo }: { onEnterDemo?: () => void }) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <section className="clay clay-card flex w-full max-w-md flex-col items-center gap-4 px-8 py-12 text-center">
        <span
          aria-hidden="true"
          className="clay clay-chip grid size-14 place-items-center text-steel"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
        </span>
        <div className="max-w-sm">
          <h1 className="text-lg font-bold tracking-tight text-ink">
            Inicia sesión para entrar al workspace
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Content Suite requiere una sesión activa. La autenticación completa llega
            con Supabase Auth en una change posterior.
          </p>
        </div>
        {onEnterDemo && (
          <button
            type="button"
            onClick={onEnterDemo}
            className="clay clay-cta px-5 py-2.5 text-sm font-semibold transition-transform duration-150 active:translate-y-px"
          >
            Explorar el shell en modo demo
          </button>
        )}
        <p className="max-w-xs text-xs leading-relaxed text-ink-soft">
          El modo demo muestra la navegación por rol con datos de presentación; no
          es autenticación ni otorga permisos.
        </p>
      </section>
    </div>
  )
}
