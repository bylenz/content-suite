import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SessionMissingState } from './StateViews'

afterEach(cleanup)

describe('SessionMissingState', () => {
  it('envía el magic link y muestra el estado "revisa tu correo" tras el envío', async () => {
    const onSignInWithMagicLink = vi.fn().mockResolvedValue(null)
    render(
      <SessionMissingState
        devRoles={[]}
        authError={null}
        onSignInWithMagicLink={onSignInWithMagicLink}
      />,
    )

    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'user@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace de acceso' }))

    expect(onSignInWithMagicLink).toHaveBeenCalledWith('user@example.com')
    await waitFor(() =>
      expect(screen.getByRole('status').textContent).toMatch(/Revisa tu correo/),
    )
  })

  it('muestra el error del envío sin quedarse en el estado "revisa tu correo"', async () => {
    const onSignInWithMagicLink = vi.fn().mockResolvedValue('Demasiados intentos, espera un momento.')
    render(
      <SessionMissingState
        devRoles={[]}
        authError={null}
        onSignInWithMagicLink={onSignInWithMagicLink}
      />,
    )

    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'user@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace de acceso' }))

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toMatch(/Demasiados intentos/),
    )
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('en desarrollo, muestra el login real y los accesos de identidad de dev a la vez', () => {
    render(
      <SessionMissingState
        devRoles={['creator']}
        authError={null}
        onEnterDemo={vi.fn()}
        onSignInWithMagicLink={vi.fn().mockResolvedValue(null)}
      />,
    )

    expect(screen.getByLabelText('Correo')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Entrar como Creator' })).not.toBeNull()
  })

  it('sin identidades de dev (build de producción), solo muestra el login real', () => {
    render(
      <SessionMissingState
        devRoles={[]}
        authError={null}
        onSignInWithMagicLink={vi.fn().mockResolvedValue(null)}
      />,
    )

    expect(screen.getByLabelText('Correo')).not.toBeNull()
    expect(screen.queryByText(/identidad de desarrollo/)).toBeNull()
  })
})
