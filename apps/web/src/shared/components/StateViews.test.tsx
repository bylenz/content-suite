import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SessionMissingState } from './StateViews'

afterEach(cleanup)

describe('SessionMissingState', () => {
  it('envía email y contraseña a onSignInWithPassword al enviar el formulario', async () => {
    const onSignInWithPassword = vi.fn().mockResolvedValue(null)
    render(
      <SessionMissingState
        devRoles={[]}
        authError={null}
        onSignInWithPassword={onSignInWithPassword}
      />,
    )

    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'secret-pass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() =>
      expect(onSignInWithPassword).toHaveBeenCalledWith('user@example.com', 'secret-pass'),
    )
  })

  it('muestra el error de credenciales devuelto por Supabase', async () => {
    const onSignInWithPassword = vi.fn().mockResolvedValue('Credenciales inválidas.')
    render(
      <SessionMissingState
        devRoles={[]}
        authError={null}
        onSignInWithPassword={onSignInWithPassword}
      />,
    )

    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toMatch(/Credenciales inválidas/),
    )
  })

  it('en desarrollo, muestra el login real y los accesos de identidad de dev a la vez', () => {
    render(
      <SessionMissingState
        devRoles={['creator']}
        authError={null}
        onEnterDemo={vi.fn()}
        onSignInWithPassword={vi.fn().mockResolvedValue(null)}
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
        onSignInWithPassword={vi.fn().mockResolvedValue(null)}
      />,
    )

    expect(screen.getByLabelText('Correo')).not.toBeNull()
    expect(screen.queryByText(/identidad de desarrollo/)).toBeNull()
  })
})
