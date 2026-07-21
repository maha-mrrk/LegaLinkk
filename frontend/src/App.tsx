import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/RequireAuth'
import {
  AnalysisLayout,
  ConsultationLayout,
  DashboardLayout,
  DocumentsLayout,
  HistoryLayout,
  SettingsLayout,
} from '@/layouts/AppLayout'
import { AnalysisPage } from '@/pages/Analysis'
import { ConsultationPage } from '@/pages/Consultation'
import { DashboardPage } from '@/pages/Dashboard'
import { DocumentsPage } from '@/pages/Documents'
import { HistoryPage } from '@/pages/History'
import { LoginPage } from '@/pages/Login'
import { SettingsPage } from '@/pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route element={<DashboardLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>

          <Route element={<ConsultationLayout />}>
            <Route path="/consultation" element={<ConsultationPage />} />
          </Route>

          <Route element={<DocumentsLayout />}>
            <Route path="/documents" element={<DocumentsPage />} />
          </Route>

          <Route element={<AnalysisLayout />}>
            <Route path="/analysis/:id" element={<AnalysisPage />} />
          </Route>

          <Route element={<HistoryLayout />}>
            <Route path="/history" element={<HistoryPage />} />
          </Route>

          <Route element={<SettingsLayout />}>
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
