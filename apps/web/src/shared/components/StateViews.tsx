import { useState, type FormEvent, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/**
 * Estados mínimos de la interfaz (carga, vacío, error).
 * Conservan la jerarquía visual del shell y usan estados semánticos legibles.
 */

export function LoadingState({ label }: { label: string }) {
  return (
    <Card
      role="status"
      aria-live="polite"
      className="mx-auto flex w-full max-w-xl flex-col items-center gap-4 px-8 py-12 text-center"
    >
      <span
        aria-hidden="true"
        className="clay-dot animate-pulse-soft size-4 bg-steel"
      />
      <p className="text-sm font-semibold text-ink">{label}</p>
      <p className="text-xs text-ink-muted">Un momento, por favor.</p>
    </Card>
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
    <Card className="flex flex-col items-center gap-5 px-8 py-10 text-center">
      <span
        aria-hidden="true"
        className="clay-icon animate-float-soft size-16 rounded-[18px] text-steel"
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
    </Card>
  )
}

/**
 * Estado de falta de permiso (403 del backend): la membresía y el rol se
 * resuelven siempre en el backend; la interfaz nunca asume acceso.
 */
export function PermissionState({
  title = 'No tienes acceso a esta marca',
  description = 'Tu identidad no tiene membresía en este workspace. Los permisos se resuelven en el backend; cambia de identidad si corresponde.',
}: {
  title?: string
  description?: string
}) {
  return (
    <Card
      role="alert"
      className="flex flex-col items-center gap-4 px-8 py-10 text-center"
    >
      <span
        aria-hidden="true"
        className="clay-icon size-12 rounded-[14px] bg-info-bg text-info-fg"
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
          <rect x="4" y="10" width="16" height="10" rx="2" />
          <path d="M8 10V7a4 4 0 0 1 8 0v3" />
        </svg>
      </span>
      <div className="max-w-md">
        <h2 className="text-base font-bold text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{description}</p>
      </div>
    </Card>
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
    <Card
      role="alert"
      className="flex flex-col items-center gap-4 px-8 py-10 text-center"
    >
      <span
        aria-hidden="true"
        className="clay-icon size-12 rounded-[14px] bg-danger-bg text-danger-fg"
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
        <Button type="button" onClick={onRetry}>
          Reintentar
        </Button>
      )}
      {children}
    </Card>
  )
}

/**
 * Formulario de login por correo + contraseña (Supabase Auth): único
 * mecanismo de entrada en producción. Las cuentas se aprovisionan a mano
 * (no hay self-signup); un error de credenciales se muestra tal cual lo
 * devuelve Supabase.
 */
function PasswordForm({
  onSignInWithPassword,
}: {
  onSignInWithPassword: (email: string, password: string) => Promise<string | null>
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phase, setPhase] = useState<'idle' | 'sending'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPhase('sending')
    setError(null)
    const message = await onSignInWithPassword(email, password)
    setPhase('idle')
    if (message) {
      setError(message)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3 text-left">
      <Label htmlFor="password-login-email" className="sr-only">
        Correo
      </Label>
      <Input
        id="password-login-email"
        type="email"
        required
        autoComplete="email"
        placeholder="tu@empresa.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Label htmlFor="password-login-password" className="sr-only">
        Contraseña
      </Label>
      <Input
        id="password-login-password"
        type="password"
        required
        autoComplete="current-password"
        placeholder="Contraseña"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <Button type="submit" disabled={phase === 'sending'}>
        {phase === 'sending' ? 'Entrando…' : 'Entrar'}
      </Button>
      {error && (
        <p role="alert" className="text-xs leading-relaxed text-danger-fg">
          {error}
        </p>
      )}
    </form>
  )
}

/**
 * Vista anónima: el visitante sin sesión no ve el shell. El único mecanismo
 * de entrada es el login real (correo + contraseña de Supabase Auth); la
 * identidad, las membresías y el rol se resuelven después en el backend con
 * `GET /api/v1/me`, nunca con datos locales.
 */
export function SessionMissingState({
  authError,
  onSignInWithPassword,
}: {
  authError: string | null
  onSignInWithPassword: (email: string, password: string) => Promise<string | null>
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <Card className="flex w-full max-w-md flex-col items-center gap-5 px-8 py-12 text-center">
        <span
          aria-hidden="true"
          className="clay-icon animate-float-soft size-16 rounded-[18px] text-steel"
        >
          <svg
            width="26"
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
            Content Suite requiere una sesión activa. Ingresa con el correo y la
            contraseña de tu cuenta.
          </p>
        </div>
        <PasswordForm onSignInWithPassword={onSignInWithPassword} />
        {authError && (
          <p role="alert" className="max-w-xs text-xs leading-relaxed text-danger-fg">
            No se pudo autenticar la sesión ({authError}). Vuelve a iniciar sesión.
          </p>
        )}
      </Card>
    </div>
  )
}
