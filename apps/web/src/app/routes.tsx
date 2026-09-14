import { Navigate, Route, Routes } from 'react-router'
import { AppLayout } from '../features/shell/AppLayout'
import { RequireSession } from '../features/session/RequireSession'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { NotFoundPage } from '../features/dashboard/NotFoundPage'
import { BrandDnaPage } from '../features/brand-dna/BrandDnaPage'
import { BrandDnaCreatePage } from '../features/brand-dna/BrandDnaCreatePage'
import { BrandDnaEditPage } from '../features/brand-dna/BrandDnaEditPage'
import { BrandDnaVersionPage } from '../features/brand-dna/BrandDnaVersionPage'
import { ObservabilityPage } from '../features/observability/ObservabilityPage'
import { CreativeStudioPage } from '../features/creative/CreativeStudioPage'
import { CreativeCreatePage } from '../features/creative/CreativeCreatePage'
import { CreativeItemPage } from '../features/creative/CreativeItemPage'
import { ApprovalsQueuePage } from '../features/approvals/ApprovalsQueuePage'
import { ApprovalDetailPage } from '../features/approvals/ApprovalDetailPage'

export function AppRoutes() {
  return (
    <Routes>
      {/* El guard vive fuera del layout: un visitante anónimo nunca ve la
          navegación por rol ni el shell. */}
      <Route element={<RequireSession />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/brand-dna" element={<BrandDnaPage />} />
          <Route path="/brand-dna/create" element={<BrandDnaCreatePage />} />
          <Route path="/brand-dna/edit" element={<BrandDnaEditPage />} />
          <Route path="/brand-dna/versions/:version" element={<BrandDnaVersionPage />} />
          <Route path="/observability" element={<ObservabilityPage />} />
          <Route path="/creative" element={<CreativeStudioPage />} />
          <Route path="/creative/new" element={<CreativeCreatePage />} />
          <Route path="/creative/items/:itemId" element={<CreativeItemPage />} />
          <Route path="/approvals" element={<ApprovalsQueuePage />} />
          <Route path="/approvals/:itemId" element={<ApprovalDetailPage />} />
        </Route>
      </Route>
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  )
}
