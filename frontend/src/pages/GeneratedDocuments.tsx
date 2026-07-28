import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  Download,
  Eye,
  FileOutput,
  FileText,
  Loader2,
  Search,
  Trash2,
  X,
} from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import {
  useDeleteGeneratedDocument,
  useGeneratedDocuments,
} from '@/hooks/useGeneratedDocuments'
import { fetchGeneratedDocumentBlob } from '@/services/generatedDocuments'
import type { GeneratedDocumentItem } from '@/types'

function formatDate(value: string) {
  return new Date(value).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSize(bytes: number) {
  return `${Math.max(1, Math.round(bytes / 1024))} Ko`
}

export function GeneratedDocumentsPage() {
  const [params] = useSearchParams()
  const contractId = params.get('contractId')
  const { data, isLoading, isError } = useGeneratedDocuments(contractId)
  const remove = useDeleteGeneratedDocument()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const contractName = data?.[0]?.sourceDocumentFilename
  const filteredDocuments = useMemo(() => {
    const normalize = (value: string) =>
      value
        .normalize('NFD')
        .replace(/\p{Diacritic}/gu, '')
        .toLowerCase()
    const query = normalize(search.trim())
    if (!query) return data ?? []
    return (data ?? []).filter((item) =>
      normalize(
        [
          item.title,
          item.filename,
          item.sourceDocumentFilename ?? '',
          item.question ?? '',
          item.createdAt,
          formatDate(item.createdAt),
          new Date(item.createdAt).toLocaleDateString('fr-FR'),
          item.kind === 'analysis_export'
            ? 'rapport analyse'
            : 'document consultation',
        ].join(' '),
      ).includes(query),
    )
  }, [data, search])

  const openFile = async (
    item: GeneratedDocumentItem,
    download: boolean,
  ) => {
    setBusy(item.id)
    setError(null)
    try {
      const blob = await fetchGeneratedDocumentBlob(item.id)
      const url = URL.createObjectURL(blob)
      if (download) {
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = item.filename
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
      } else {
        window.open(url, '_blank', 'noopener,noreferrer')
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setError("Impossible d'ouvrir ce document.")
    } finally {
      setBusy(null)
    }
  }

  const deleteItem = (item: GeneratedDocumentItem) => {
    if (!window.confirm(`Supprimer « ${item.title} » ?`)) return
    remove.mutate(item.id)
  }

  return (
    <div className="space-y-6">
      {contractId ? (
        <Card padding="md">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                Filtre actif
              </p>
              <p className="mt-1 text-sm text-slate-700">
                Rapports associés à{' '}
                <strong>{contractName ?? 'ce contrat'}</strong>
              </p>
            </div>
            <Link to="/generated-documents">
              <Button size="sm" variant="outline">
                <X className="size-4" />
                Voir tous les documents
              </Button>
            </Link>
          </div>
        </Card>
      ) : null}

      <Card padding="lg">
        <CardHeader
          title="Bibliothèque des documents générés"
          subtitle="Tous vos rapports PDF, regroupés et accessibles à tout moment"
        />

        <div className="relative mb-5">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Rechercher par contrat, titre, contenu ou date…"
            aria-label="Rechercher un document généré"
            className="w-full rounded-xl border border-border bg-slate-50 py-2.5 pl-10 pr-10 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-brand focus:bg-white focus:ring-2 focus:ring-brand/15"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch('')}
              aria-label="Effacer la recherche"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            >
              <X className="size-3.5" />
            </button>
          ) : null}
        </div>

        {error || isError ? (
          <p className="mb-4 flex items-center gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            <AlertTriangle className="size-4" />
            {error ?? 'Impossible de charger les documents générés.'}
          </p>
        ) : null}

        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.length ? (
          <EmptyState
            icon={<FileOutput className="size-6" />}
            title={
              contractId
                ? 'Aucun rapport pour ce contrat'
                : 'Aucun document généré'
            }
            description="Les PDF exportés depuis une consultation ou une analyse apparaîtront automatiquement ici."
          />
        ) : !filteredDocuments.length ? (
          <EmptyState
            icon={<Search className="size-6" />}
            title="Aucun rapport trouvé"
            description={`Aucun document ne correspond à « ${search.trim()} ». Essayez le nom du contrat, un mot du titre ou une date.`}
          />
        ) : (
          <ul className="space-y-3">
            {filteredDocuments.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-white px-4 py-3 transition hover:border-brand/30 hover:shadow-sm"
              >
                <button
                  type="button"
                  onClick={() => openFile(item, false)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-500">
                    <FileText className="size-5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-slate-900">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted">
                      {item.kind === 'analysis_export'
                        ? 'Rapport d’analyse'
                        : 'Document de consultation'}
                      {' · '}
                      {formatDate(item.createdAt)} · {formatSize(item.fileSize)}
                    </span>
                    {item.sourceDocumentFilename ? (
                      <span className="mt-1 block truncate text-xs font-medium text-brand">
                        Contrat : {item.sourceDocumentFilename}
                      </span>
                    ) : null}
                  </span>
                </button>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => openFile(item, false)}
                    disabled={busy === item.id}
                  >
                    {busy === item.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                    Voir
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openFile(item, true)}
                    disabled={busy === item.id}
                  >
                    <Download className="size-4" />
                    Télécharger
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => deleteItem(item)}
                    disabled={remove.isPending}
                    className="text-danger hover:bg-danger-soft"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
