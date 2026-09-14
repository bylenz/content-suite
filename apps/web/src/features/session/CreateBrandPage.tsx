import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '../../shared/api/client'
import { useCreateBrand } from './api'
import { useSession } from './useSession'

/**
 * Alta self-serve de workspace (`POST /brands`): quien crea la marca se
 * vuelve automáticamente su CREATOR (ver API.md "Workspaces").
 *
 * Dos contextos con el mismo formulario:
 * - Onboarding: identidad autenticada sin ninguna membresía
 *   (`profile.activeMembership === null`). `AppLayout` la muestra en vez de
 *   un shell vacío; tras el 201, `refreshProfile(brand_id)` activa la nueva
 *   marca y el shell aparece por sí solo.
 * - Desde el shell (`/workspaces/new`): la identidad ya tiene marcas y crea
 *   otra. Tras el 201 se activa la nueva marca y se vuelve al Dashboard.
 */
export function CreateBrandPage() {
  const [name, setName] = useState('')
  const { profile, refreshProfile } = useSession()
  const navigate = useNavigate()
  const createBrand = useCreateBrand()
  const hasWorkspaces = (profile?.memberships.length ?? 0) > 0

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    let brandId: string
    try {
      const membership = await createBrand.mutateAsync(name.trim())
      brandId = membership.brand_id
    } catch {
      // El error queda en `createBrand.error` (react-query) y se muestra
      // abajo; nada más que hacer aquí.
      return
    }
    await refreshProfile(brandId)
    if (hasWorkspaces) navigate('/', { replace: true })
  }

  const errorMessage =
    createBrand.error instanceof ApiError
      ? createBrand.error.code === 'PERMISSION_DENIED' || createBrand.error.status === 403
        ? 'Tu cuenta no está autorizada para crear workspaces.'
        : createBrand.error.message
      : createBrand.error
        ? 'No se pudo crear el workspace.'
        : null

  return (
    <div
      className={
        hasWorkspaces
          ? 'flex justify-center py-6'
          : 'flex min-h-dvh items-center justify-center bg-canvas px-4 py-10'
      }
    >
      <Card className="flex w-full max-w-md flex-col items-center gap-4 px-8 py-12 text-center">
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
            <path d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <div className="max-w-sm">
          <h1 className="text-lg font-bold tracking-tight text-ink">
            {hasWorkspaces ? 'Crea un nuevo workspace' : 'Crea tu primer workspace'}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            {hasWorkspaces
              ? 'Cada workspace es una marca con su propio Brand DNA y contenido. Serás su Creator.'
              : 'Tu cuenta todavía no pertenece a ninguna marca. Dale un nombre a tu workspace y te volverás su Creator.'}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3 text-left">
          <div className="flex flex-col gap-2">
            <Label htmlFor="brand-name" className="sr-only">
              Nombre de la marca
            </Label>
            <Input
              id="brand-name"
              required
              minLength={1}
              maxLength={200}
              placeholder="Nombre de tu marca"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
            />
          </div>
          <Button type="submit" disabled={createBrand.isPending || name.trim().length === 0}>
            {createBrand.isPending ? 'Creando…' : 'Crear workspace'}
          </Button>
          {errorMessage && (
            <p role="alert" className="text-xs leading-relaxed text-danger-fg">
              {errorMessage}
            </p>
          )}
        </form>
        {hasWorkspaces && (
          <Link to="/" className="text-[12.5px] font-semibold text-ink-soft hover:text-steel">
            ← Volver al Dashboard
          </Link>
        )}
      </Card>
    </div>
  )
}
