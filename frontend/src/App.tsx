import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import {
  AgentsLayout,
  AnalysisLayout,
  ConsultationLayout,
  DashboardLayout,
  DocumentsLayout,
  HistoryLayout,
  SettingsLayout,
  SupervisionLayout,
} from '@/layouts/AppLayout'
import { AgentDetailPage } from '@/pages/AgentDetail'
import { AnalysisPage } from '@/pages/Analysis'
import { ConsultationPage } from '@/pages/Consultation'
import { DashboardPage } from '@/pages/Dashboard'
import { DocumentsPage } from '@/pages/Documents'
import { HistoryPage } from '@/pages/History'
import { LoginPage } from '@/pages/Login'
import { SettingsPage } from '@/pages/Settings'
import { SupervisionPage } from '@/pages/Supervision'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />

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

        <Route element={<AgentsLayout />}>
          <Route path="/agents/:id" element={<AgentDetailPage />} />
        </Route>

        <Route element={<SupervisionLayout />}>
          <Route path="/supervision" element={<SupervisionPage />} />
        </Route>

        <Route element={<SettingsLayout />}>
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
