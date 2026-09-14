import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { apiFetch } from '../../shared/api/client'
import type { BrandAssetList, BrandAssetOut } from '../../shared/api/types'
import { BrandAssetsPanel } from './BrandAssetsPanel'

// Solo se simula la capa de red; el flujo real (subir/reemplazar/eliminar +
// invalidación de la lista) se ejerce contra el componente real.
vi.mock('../../shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shared/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const fetchMock = vi.mocked(apiFetch)

;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

const BRAND_ID = 'brand-1'

function renderPanel(isCreator: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrandAssetsPanel brandId={BRAND_ID} isCreator={isCreator} />
    </QueryClientProvider>,
  )
}

function primaryLogo(overrides: Partial<BrandAssetOut> = {}): BrandAssetOut {
  return {
    id: 'asset-1',
    brand_id: BRAND_ID,
    brand_dna_version_id: null,
    type: 'PRIMARY_LOGO',
    signed_url: 'https://storage.example/signed/logo.png',
    metadata: { content_type: 'image/png' },
    created_at: '2026-09-14T10:00:00Z',
    ...overrides,
  }
}

function pngFile(name = 'logo.png'): File {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
})

describe('BrandAssetsPanel', () => {
  it('muestra los tres slots vacíos cuando la marca no tiene assets', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [] } satisfies BrandAssetList)
    renderPanel(true)

    expect(await screen.findByText('Primary Logo')).toBeDefined()
    expect(screen.getByText('Alternative Logo')).toBeDefined()
    expect(screen.getByText('Visual References')).toBeDefined()
    expect(screen.getAllByText('Sin subir')).toHaveLength(2)
    expect(screen.getByText('0 images')).toBeDefined()
    expect(screen.getAllByText('Subir')).toHaveLength(2)
    expect(screen.getByText('Agregar')).toBeDefined()
  })

  it('un no-Creator no ve controles de escritura', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [primaryLogo()] } satisfies BrandAssetList)
    renderPanel(false)

    expect(await screen.findByText('Primary Logo')).toBeDefined()
    expect(screen.queryByText('Reemplazar')).toBeNull()
    expect(screen.queryByText('Eliminar')).toBeNull()
    expect(screen.queryByText('Agregar')).toBeNull()
  })

  it('sube el primer Primary Logo (POST multipart con type + file)', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [] } satisfies BrandAssetList)
    renderPanel(true)
    expect(await screen.findByText('Primary Logo')).toBeDefined()

    fetchMock.mockResolvedValueOnce(primaryLogo())
    fetchMock.mockResolvedValueOnce({ assets: [primaryLogo()] } satisfies BrandAssetList)

    const file = pngFile()
    const input = screen.getByLabelText('Subir Primary Logo') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByText('Reemplazar')).toBeDefined()
    })

    const [path, init] = fetchMock.mock.calls[1]
    expect(path).toBe(`/api/v1/brands/${BRAND_ID}/assets`)
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body.get('type')).toBe('PRIMARY_LOGO')
    expect(body.get('file')).toBeInstanceOf(File)

    expect(await screen.findByText('Brand asset subido correctamente.')).toBeDefined()
  })

  it('reemplaza un Primary Logo existente (mismo botón, ya dice Reemplazar)', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [primaryLogo()] } satisfies BrandAssetList)
    renderPanel(true)
    expect(await screen.findByText('Reemplazar')).toBeDefined()

    const replaced = primaryLogo({ id: 'asset-2', signed_url: 'https://storage.example/signed/v2.png' })
    fetchMock.mockResolvedValueOnce(replaced)
    fetchMock.mockResolvedValueOnce({ assets: [replaced] } satisfies BrandAssetList)

    const input = screen.getByLabelText('Reemplazar Primary Logo') as HTMLInputElement
    fireEvent.change(input, { target: { files: [pngFile('logo-v2.png')] } })

    await waitFor(() => {
      const [, init] = fetchMock.mock.calls[1]
      expect((init as RequestInit).method).toBe('POST')
    })
    expect(await screen.findByText('Brand asset subido correctamente.')).toBeDefined()
  })

  it('elimina un asset (DELETE) y refresca la lista', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [primaryLogo()] } satisfies BrandAssetList)
    renderPanel(true)
    expect(await screen.findByText('Eliminar')).toBeDefined()

    fetchMock.mockResolvedValueOnce(undefined)
    fetchMock.mockResolvedValueOnce({ assets: [] } satisfies BrandAssetList)

    fireEvent.click(screen.getByText('Eliminar'))

    await waitFor(() => {
      const [path, init] = fetchMock.mock.calls[1]
      expect(path).toBe(`/api/v1/brands/${BRAND_ID}/assets/asset-1`)
      expect((init as RequestInit).method).toBe('DELETE')
    })
    expect(await screen.findByText('Brand asset eliminado.')).toBeDefined()
    expect(await screen.findAllByText('Sin subir')).toHaveLength(2)
  })

  it('agrega múltiples Visual References y las lista todas', async () => {
    const refs: BrandAssetOut[] = [
      primaryLogo({ id: 'ref-1', type: 'VISUAL_REFERENCE' }),
      primaryLogo({ id: 'ref-2', type: 'VISUAL_REFERENCE' }),
    ]
    fetchMock.mockResolvedValueOnce({ assets: refs } satisfies BrandAssetList)
    renderPanel(true)

    expect(await screen.findByText('2 images')).toBeDefined()
    expect(screen.getAllByLabelText('Eliminar referencia visual')).toHaveLength(2)
  })

  it('muestra un error inline si el upload falla (p. ej. 422 de validación)', async () => {
    fetchMock.mockResolvedValueOnce({ assets: [] } satisfies BrandAssetList)
    renderPanel(true)
    expect(await screen.findByText('Primary Logo')).toBeDefined()

    const { ApiError } = await import('../../shared/api/client')
    fetchMock.mockRejectedValueOnce(
      new ApiError('Uploaded file is not a recognized PNG, JPEG or WebP image', 422, 'VALIDATION_ERROR'),
    )

    const input = screen.getByLabelText('Subir Primary Logo') as HTMLInputElement
    fireEvent.change(input, { target: { files: [pngFile()] } })

    expect(
      await screen.findByText('Uploaded file is not a recognized PNG, JPEG or WebP image'),
    ).toBeDefined()
  })
})
