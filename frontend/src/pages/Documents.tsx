import { useState, type ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Download,
  Eye,
  FileText,
  Files,
  Loader2,
  Trash2,
  Upload,
} from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { IngestionProgress } from '@/components/IngestionProgress'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { StatusBadge } from '@/components/StatusBadge'
import { UploadZone } from '@/components/UploadZone'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { useDeleteDocument, useDocuments, useUploadDocument } from '@/hooks/useDocuments'
import { fetchDocumentBlob } from '@/services/documents'
import type { DocumentItem } from '@/types'
import { cn } from '@/lib/cn'

interface ActiveUpload {
  documentId: string
  filename: string
}

/** Small icon-only action button used in each library row. */
function IconAction({
  title,
  icon: Icon,
  onClick,
  busy,
  danger,
}: {
  title: string
  icon: ComponentType<{ className?: string }>
  onClick: () => void
  busy?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={busy}
      className={cn(
        'inline-flex size-8 items-center justify-center rounded-lg text-slate-500 transition disabled:opacity-50',
        danger
          ? 'hover:bg-danger-soft hover:text-danger'
          : 'hover:bg-primary-soft hover:text-primary',
      )}
    >
      {busy ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Icon className="size-4" />
      )}
    </button>
  )
}

export function DocumentsPage() {
  const { data, isLoading } = useDocuments()
  const upload = useUploadDocument()
  const remove = useDeleteDocument()
  const queryClient = useQueryClient()
  const [activeUploads, setActiveUploads] = useState<ActiveUpload[]>([])
  const [busy, setBusy] = useState<{ id: string; action: 'view' | 'download' } | null>(
    null,
  )
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const refreshLists = () => {
    void queryClient.invalidateQueries({ queryKey: ['documents'] })
    void queryClient.invalidateQueries({ queryKey: ['activity'] })
  }

  const handleFiles = (files: File[]) => {
    const file = files[0]
    if (!file) return
    upload.mutate(file, {
      onSuccess: (result) => {
        setActiveUploads((prev) =>
          [
            { documentId: result.documentId, filename: result.filename },
            ...prev.filter((u) => u.documentId !== result.documentId),
          ].slice(0, 5),
        )
      },
    })
  }

  const pdfName = (filename: string) =>
    filename.toLowerCase().endsWith('.pdf') ? filename : `${filename}.pdf`

  const openBlob = async (doc: DocumentItem, action: 'view' | 'download') => {
    setActionError(null)
    setBusy({ id: doc.id, action })
    try {
      const blob = await fetchDocumentBlob(doc.id)
      const url = URL.createObjectURL(blob)
      if (action === 'view') {
        window.open(url, '_blank', 'noopener,noreferrer')
      } else {
        const link = document.createElement('a')
        link.href = url
        link.download = pdfName(doc.filename)
        document.body.appendChild(link)
        link.click()
        link.remove()
      }
      // Revoke later so the new tab / download has time to read the blob.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setActionError(
        "Impossible d'ouvrir le PDF. Le fichier est peut-être introuvable.",
      )
    } finally {
      setBusy(null)
    }
  }

  const handleDelete = (doc: DocumentItem) => {
    const confirmed = window.confirm(
      `Supprimer définitivement « ${doc.filename} » ? Cette action est irréversible.`,
    )
    if (!confirmed) return
    setActionError(null)
    setPendingDelete(doc.id)
    remove.mutate(doc.id, {
      onError: () =>
        setActionError('La suppression a échoué. Veuillez réessayer.'),
      onSettled: () => setPendingDelete(null),
    })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-1" padding="lg">
        <CardHeader
          title="Importer un contrat"
          subtitle="Formats acceptés : PDF · jusqu’à 25 Mo"
        />
        <UploadZone onFiles={handleFiles} />

        {upload.isPending ? (
          <p className="mt-3 text-xs text-brand">Envoi du document…</p>
        ) : null}

        {upload.isError ? (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5" />
            {upload.error instanceof Error
              ? upload.error.message
              : "L'envoi a échoué. Veuillez réessayer."}
          </p>
        ) : null}

        {activeUploads.map((item) => (
          <IngestionProgress
            key={item.documentId}
            documentId={item.documentId}
            filename={item.filename}
            onCompleted={refreshLists}
            onFailed={refreshLists}
          />
        ))}
      </Card>

      <Card className="lg:col-span-2" padding="lg">
        <CardHeader title="Bibliothèque" subtitle="Tous vos PDF analysés" />

        {actionError ? (
          <p className="mb-3 flex items-center gap-1.5 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger">
            <AlertTriangle className="size-3.5 shrink-0" />
            {actionError}
          </p>
        ) : null}

        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.length ? (
          <EmptyState
            title="Aucun contrat"
            description="Déposez votre premier contrat (PDF) pour démarrer une analyse."
            icon={<Upload className="size-6" />}
          />
        ) : (
          <ul className="space-y-3">
            {data.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-white px-4 py-3 transition hover:border-brand/30 hover:shadow-sm"
              >
                <button
                  type="button"
                  onClick={() => openBlob(doc, 'view')}
                  title="Visualiser le PDF"
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <div className="flex size-10 items-center justify-center rounded-lg bg-red-50 text-red-500">
                    <FileText className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900 hover:text-primary">
                      {doc.filename}
                    </p>
                    <p className="text-xs text-muted">
                      {doc.type} · {doc.date}
                    </p>
                  </div>
                </button>
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={doc.status} />
                  <div className="flex items-center gap-0.5">
                    <IconAction
                      title="Visualiser le PDF"
                      icon={Eye}
                      onClick={() => openBlob(doc, 'view')}
                      busy={busy?.id === doc.id && busy.action === 'view'}
                    />
                    <IconAction
                      title="Télécharger le PDF"
                      icon={Download}
                      onClick={() => openBlob(doc, 'download')}
                      busy={busy?.id === doc.id && busy.action === 'download'}
                    />
                    <IconAction
                      title="Supprimer le contrat"
                      icon={Trash2}
                      onClick={() => handleDelete(doc)}
                      busy={pendingDelete === doc.id}
                      danger
                    />
                  </div>
                  <Link to={`/analysis/${doc.id}`}>
                    <Button size="sm" variant="outline">
                      Voir l’analyse
                    </Button>
                  </Link>
                  <Link to={`/generated-documents?contractId=${doc.id}`}>
                    <Button size="sm" variant="outline">
                      <Files className="size-4" />
                      Rapports générés
                    </Button>
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
