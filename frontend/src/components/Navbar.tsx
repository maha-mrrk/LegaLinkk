import { Menu, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'

interface NavbarProps {
  title?: string
  subtitle?: string
  onMenuClick?: () => void
}

export function Navbar({ title, subtitle, onMenuClick }: NavbarProps) {
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
          ) : null}
        </div>

        <div className="ml-auto flex items-center gap-2">
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
