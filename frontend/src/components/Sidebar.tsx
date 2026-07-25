import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquarePlus,
  FileText,
  Clock,
  Settings,
  LogOut,
  X,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/cn'

const navItems = [
  { to: '/dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/consultation', label: 'Nouvelle consultation', icon: MessageSquarePlus },
  { to: '/documents', label: 'Mes contrats', icon: FileText },
  { to: '/history', label: 'Historique', icon: Clock },
  { to: '/settings', label: 'Paramètres', icon: Settings },
]

interface SidebarProps {
  open?: boolean
  onClose?: () => void
}

export function Sidebar({ open = false, onClose }: SidebarProps) {
  const { user, initials, logout } = useAuth()
  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-40 bg-navy/40 backdrop-blur-sm transition-opacity lg:hidden',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        onClick={onClose}
      />
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-gradient-to-b from-navy via-navy-soft to-primary text-white transition-transform duration-300 lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2.5">
            <Logo className="size-9" />
            <div>
              <p className="text-base font-bold tracking-tight">LegalLink</p>
              <p className="text-[10px] font-medium uppercase tracking-wider text-white/50">
                Intelligence juridique
              </p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1.5 text-white/60 hover:bg-white/10 lg:hidden"
            onClick={onClose}
            aria-label="Fermer le menu"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin">
          <p className="px-3 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-wider text-white/40">
            Menu
          </p>
          <div className="space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-white/15 text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        'size-4 shrink-0',
                        isActive ? 'text-white' : 'text-white/60',
                      )}
                    />
                    <span>{label}</span>
                    {isActive ? (
                      <span className="ml-auto size-1.5 rounded-full bg-white" />
                    ) : null}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="flex items-center gap-3 rounded-xl bg-white/5 p-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-white">
              {initials || '—'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">
                {user?.full_name || user?.email || 'Utilisateur'}
              </p>
              <p className="truncate text-xs text-white/50">{user?.role}</p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg p-1.5 text-white/60 transition hover:bg-white/10 hover:text-white"
              aria-label="Se déconnecter"
              title="Se déconnecter"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
