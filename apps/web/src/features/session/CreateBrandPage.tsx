import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '../../shared/api/client'
import { useCreateBrand } from './api'
import { useSession } from './useSession'

/**
 * Onboarding self-serve: una identidad autenticada sin ninguna membresía
 * (`profile.activeMembership === null`) no tiene marca activa que mostrar -- en vez
 * de dejar el shell vacío, se le ofrece crear su propio workspace. Quien crea
 * la marca se vuelve automáticamente su CREATOR (ver API.md "Workspaces").
 * Tras el 201, `refreshProfile()` vuelve a pedir `/me`: la nueva membresía
 * queda activa y `AppLayout` deja de mostrar esta pantalla por sí solo.
 */
export function CreateBrandPage() {
  const [name, setName] = useState('')
  const { refreshProfile } = useSession()
  const createBrand = useCreateBrand()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      await createBrand.mutateAsync(name)
    } catch {
      // El error queda en `createBrand.error` (react-query) y se muestra
      // abajo; nada más que hacer aquí.
      return
    }
    await refreshProfile()
  }

  const errorMessage =
    createBrand.error instanceof ApiError
      ? createBrand.error.message
      : createBrand.error
        ? 'No se pudo crear el workspace.'
        : null

  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <Card className="flex w-full max-w-md flex-col items-center gap-4 px-8 py-12 text-center">
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
            <path d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <div className="max-w-sm">
          <h1 className="text-lg font-bold tracking-tight text-ink">
            Crea tu primer workspace
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Tu cuenta todavía no pertenece a ninguna marca. Dale un nombre a tu
            workspace y te volverás su Creator.
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
      </Card>
    </div>
  )
}
