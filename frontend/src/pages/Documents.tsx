import { Link } from 'react-router-dom'
import { FileText, Upload } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { StatusBadge } from '@/components/StatusBadge'
import { UploadZone } from '@/components/UploadZone'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { useDocuments, useUploadDocument } from '@/hooks/useDocuments'

export function DocumentsPage() {
  const { data, isLoading } = useDocuments()
  const upload = useUploadDocument()

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-1" padding="lg">
        <CardHeader
          title="Importer un contrat"
          subtitle="Connecté à POST /api/v1/documents (mock actif)"
        />
        <UploadZone
          onFiles={(files) => {
            const file = files[0]
            if (file) upload.mutate(file)
          }}
        />
        {upload.isPending ? (
          <p className="mt-3 text-xs text-brand">Envoi en cours…</p>
        ) : null}
        {upload.isSuccess ? (
          <p className="mt-3 text-xs text-success">
            Document ajouté : {upload.data.filename}
          </p>
        ) : null}
      </Card>

      <Card className="lg:col-span-2" padding="lg">
        <CardHeader title="Bibliothèque" subtitle="Tous vos PDF analysés" />
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.length ? (
          <EmptyState
            title="Aucun contrat"
            description="Uploadez votre premier PDF pour démarrer une analyse."
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
