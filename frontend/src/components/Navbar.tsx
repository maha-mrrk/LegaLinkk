import { Bell, Menu, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { SearchBar } from '@/components/SearchBar'
import { Button } from '@/components/ui/Button'

interface NavbarProps {
  title?: string
  subtitle?: string
  onMenuClick?: () => void
  showSearch?: boolean
}

export function Navbar({
  title,
  subtitle,
  onMenuClick,
  showSearch = true,
}: NavbarProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-white/90 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 lg:px-6">
        <button
          type="button"
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
          onClick={onMenuClick}
          aria-label="Ouvrir le menu"
        >
          <Menu className="size-5" />
        </button>

        <div className="min-w-0 flex-1">
          {title ? (
            <div>
              <h1 className="truncate text-lg font-semibold text-slate-900 lg:text-xl">
                {title}
              </h1>
              {subtitle ? (
                <p className="truncate text-sm text-muted">{subtitle}</p>
              ) : null}
            </div>
          ) : showSearch ? (
            <SearchBar placeholder="Rechercher un contrat, un rapport…" />
          ) : null}
        </div>

        {title && showSearch ? (
          <div className="order-last w-full sm:order-none sm:w-auto sm:max-w-xs lg:max-w-sm">
            <SearchBar placeholder="Rechercher…" />
          </div>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            className="relative rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            aria-label="Notifications"
          >
            <Bell className="size-5" />
            <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-danger ring-2 ring-white" />
          </button>
          <Link to="/consultation">
            <Button size="sm" leftIcon={<Plus className="size-4" />}>
              <span className="hidden sm:inline">Nouvelle consultation</span>
              <span className="sm:hidden">Nouveau</span>
            </Button>
          </Link>
        </div>
      </div>
    </header>
  )
}
