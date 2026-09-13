import { useContext } from 'react'
import { SessionContext, type SessionContextValue } from './session-context'

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession debe usarse dentro de SessionProvider')
  return context
}
