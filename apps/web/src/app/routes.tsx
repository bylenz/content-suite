import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from '../features/shell/AppLayout'
import { RequireSession } from '../features/session/RequireSession'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { NotFoundPage } from '../features/dashboard/NotFoundPage'

export function AppRoutes() {
  return (
    <Routes>
      {/* El guard vive fuera del layout: un visitante anónimo nunca ve la
          navegación por rol ni el shell. */}
      <Route element={<RequireSession />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
        </Route>
      </Route>
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  )
}
