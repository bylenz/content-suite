import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SessionMissingState } from './StateViews'

afterEach(cleanup)

describe('SessionMissingState', () => {
  it('envía email y contraseña a onSignInWithPassword al enviar el formulario', async () => {
    const onSignInWithPassword = vi.fn().mockResolvedValue(null)
    render(
      <SessionMissingState
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

  it('solo ofrece el login real: no existe entrada con identidades de prueba', () => {
    render(
      <SessionMissingState authError={null} onSignInWithPassword={vi.fn().mockResolvedValue(null)} />,
    )

    expect(screen.getByLabelText('Correo')).not.toBeNull()
    expect(screen.queryByText(/identidad de desarrollo/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Entrar como/ })).toBeNull()
  })
})
