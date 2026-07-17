import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'

interface AppLayoutProps {
  title?: string
  subtitle?: string
  showSearch?: boolean
}

export function AppLayout({ title, subtitle, showSearch }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar
          title={title}
          subtitle={subtitle}
          showSearch={showSearch}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 overflow-x-hidden p-4 lg:p-6">
          <div className="mx-auto w-full max-w-7xl animate-in fade-in duration-300">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

/** Wrapper used by the router to inject page-specific navbar props via route handle / outlet context. */
export function DashboardLayout() {
  return (
    <AppShell
      title="Bonjour, Me. Reda El Amrani 👋"
      subtitle="Voici un aperçu de votre activité juridique aujourd’hui."
    />
  )
}

function AppShell({
  title,
  subtitle,
  showSearch = true,
}: {
  title?: string
  subtitle?: string
  showSearch?: boolean
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar
          title={title}
          subtitle={subtitle}
          showSearch={showSearch}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 overflow-x-hidden p-4 lg:p-6">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export function ConsultationLayout() {
  return <AppShell title="Nouvelle consultation" subtitle="Assistant juridique conversationnel" />
}

export function DocumentsLayout() {
  return <AppShell title="Mes contrats" subtitle="Documents uploadés et analyses associées" />
}

export function AnalysisLayout() {
  return <AppShell title="Résultat d’analyse" subtitle="Points critiques et score global" showSearch={false} />
}

export function HistoryLayout() {
  return <AppShell title="Historique" subtitle="Toutes vos analyses passées" />
}

export function AgentsLayout() {
  return <AppShell title="Agents IA" subtitle="Détail et performances des agents" showSearch={false} />
}

export function SupervisionLayout() {
  return <AppShell title="Centre de supervision IA" subtitle="Pipeline temps réel" showSearch={false} />
}

export function SettingsLayout() {
  return <AppShell title="Paramètres" subtitle="Sécurité, modèles et préférences" showSearch={false} />
}
