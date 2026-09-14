import { useMutation } from '@tanstack/react-query'
import { apiFetch } from '../../shared/api/client'
import type { Membership } from '../../shared/api/types'

/**
 * Self-serve: cualquier identidad autenticada puede crear un workspace y se
 * vuelve automáticamente su CREATOR. No requiere membresía previa (POST
 * /api/v1/brands -- ver API.md "Workspaces").
 */
export function useCreateBrand() {
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<Membership>('/api/v1/brands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      }),
  })
}
