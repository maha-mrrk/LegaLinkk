import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, FileText, Upload } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { IngestionProgress } from '@/components/IngestionProgress'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { StatusBadge } from '@/components/StatusBadge'
import { UploadZone } from '@/components/UploadZone'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { useDocuments, useUploadDocument } from '@/hooks/useDocuments'

interface ActiveUpload {
  documentId: string
  filename: string
}

export function DocumentsPage() {
  const { data, isLoading } = useDocuments()
  const upload = useUploadDocument()
  const queryClient = useQueryClient()
  const [activeUploads, setActiveUploads] = useState<ActiveUpload[]>([])

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
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-red-50 text-red-500">
                    <FileText className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {doc.filename}
                    </p>
                    <p className="text-xs text-muted">
                      {doc.type} · {doc.date}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={doc.status} />
                  <Link to={`/analysis/${doc.id}`}>
                    <Button size="sm" variant="outline">
                      Voir l’analyse
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
