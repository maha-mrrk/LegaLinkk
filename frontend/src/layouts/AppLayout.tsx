import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { useAuth } from '@/context/AuthContext'

function AppShell({ title, subtitle }: { title?: string; subtitle?: string }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar
          title={title}
          subtitle={subtitle}
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

export function DashboardLayout() {
  const { user } = useAuth()
  const name = user?.full_name || user?.email || ''
  return (
    <AppShell
      title={name ? `Bonjour, ${name} 👋` : 'Tableau de bord'}
      subtitle="Voici un aperçu de votre activité juridique."
    />
  )
}

export function ConsultationLayout() {
  return <AppShell title="Nouvelle consultation" subtitle="Votre assistant juridique" />
}

export function DocumentsLayout() {
  return <AppShell title="Mes contrats" subtitle="Vos contrats déposés et leurs analyses" />
}

export function AnalysisLayout() {
  return <AppShell title="Résultat d’analyse" subtitle="Points critiques et niveau de risque" />
}

export function HistoryLayout() {
  return <AppShell title="Historique" subtitle="Toutes vos analyses passées" />
}

export function SettingsLayout() {
  return <AppShell title="Paramètres" subtitle="Votre compte" />
}
