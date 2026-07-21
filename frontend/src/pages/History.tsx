import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, FileText } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { SearchBar } from '@/components/SearchBar'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useDocuments } from '@/hooks/useDocuments'
import type { DocumentStatus } from '@/types'

export function HistoryPage() {
  const { data, isLoading } = useDocuments()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<'all' | DocumentStatus>('all')
  const [page, setPage] = useState(1)
  const pageSize = 5

  const filtered = useMemo(() => {
    const list = data ?? []
    return list.filter((doc) => {
      const matchQuery = doc.filename
        .toLowerCase()
        .includes(query.toLowerCase())
      const matchStatus = status === 'all' || doc.status === status
      return matchQuery && matchStatus
    })
  }, [data, query, status])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="space-y-4">
      <Card padding="md">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <SearchBar
            value={query}
            onChange={(v) => {
              setQuery(v)
              setPage(1)
            }}
            placeholder="Rechercher un fichier…"
            className="max-w-none flex-1"
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as 'all' | DocumentStatus)
              setPage(1)
            }}
            className="h-11 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
          >
            <option value="all">Tous les statuts</option>
            <option value="completed">Terminé</option>
            <option value="processing">En cours</option>
            <option value="queued">En file</option>
            <option value="failed">Échec</option>
          </select>
          <select className="h-11 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/20">
            <option>Période : 30 jours</option>
            <option>7 jours</option>
            <option>90 jours</option>
          </select>
        </div>
      </Card>

      <Card padding="none" className="overflow-hidden">
        {isLoading ? (
          <LoadingSpinner />
        ) : pageItems.length === 0 ? (
          <EmptyState
            title="Aucun document"
            description="Aucun résultat pour ces filtres."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Fichier</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Assistants</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="px-4 py-3 font-medium">Statut</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((doc) => (
                  <tr
                    key={doc.id}
                    className="border-t border-border transition hover:bg-slate-50/80"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 text-red-500" />
                        <span className="font-medium text-slate-900">
                          {doc.filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{doc.type}</td>
                    <td className="px-4 py-3 text-slate-600">{doc.date}</td>
                    <td className="px-4 py-3">
                      <div className="flex -space-x-1.5">
                        {doc.agents.map((agent) => (
                          <span
                            key={agent}
                            className="flex size-7 items-center justify-center rounded-full bg-brand text-[10px] font-semibold text-white ring-2 ring-white"
                          >
                            {agent}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-900">
                      {doc.score > 0 ? doc.score : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Link to={`/analysis/${doc.id}`}>
                          <Button variant="ghost" size="sm" aria-label="Voir">
                            <Eye className="size-4" />
                          </Button>
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <p className="text-xs text-muted">
            {filtered.length} document{filtered.length > 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setPage(n)}
                className={`size-8 rounded-lg text-sm font-medium transition ${
                  page === n
                    ? 'bg-brand text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {n}
              </button>
            ))}
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="size-8 rounded-lg text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      </Card>
    </div>
  )
}
