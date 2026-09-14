import { BrowserRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { SessionProvider } from '../features/session/SessionProvider'
import { AppRoutes } from './routes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    // reducedMotion="user": respeta prefers-reduced-motion desactivando
    // transform/layout de todos los motion components (opacidad/color se
    // conservan como feedback).
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <BrowserRouter>{children}</BrowserRouter>
        </SessionProvider>
      </QueryClientProvider>
    </MotionConfig>
  )
}

export function App() {
  return (
    <AppProviders>
      <AppRoutes />
    </AppProviders>
  )
}
