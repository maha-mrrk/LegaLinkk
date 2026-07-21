import { useMemo } from 'react'
import { CheckCircle2, Clock, FileText, XCircle } from 'lucide-react'
import { DocumentCard } from '@/components/DocumentCard'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { Card, CardHeader } from '@/components/ui/Card'
import { useDocuments, useRecentActivity } from '@/hooks/useDocuments'

export function DashboardPage() {
  const { data: documents } = useDocuments()
  const { data: activity, isLoading } = useRecentActivity()

  const stats = useMemo(() => {
    const list = documents ?? []
    return {
      total: list.length,
      ready: list.filter((d) => d.indexed).length,
      processing: list.filter(
        (d) => d.status === 'processing' || d.status === 'pending',
      ).length,
      failed: list.filter((d) => d.status === 'failed').length,
    }
  }, [documents])

  const cards = [
    {
      label: 'Contrats déposés',
      value: stats.total,
      icon: FileText,
      color: 'text-brand',
      bg: 'bg-brand-soft',
    },
    {
      label: 'Prêts à analyser',
      value: stats.ready,
      icon: CheckCircle2,
      color: 'text-success',
      bg: 'bg-emerald-50',
    },
    {
      label: 'En traitement',
      value: stats.processing,
      icon: Clock,
      color: 'text-warning',
      bg: 'bg-amber-50',
    },
    {
      label: 'Échecs',
      value: stats.failed,
      icon: XCircle,
      color: 'text-danger',
      bg: 'bg-red-50',
    },
  ]

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((stat) => (
          <Card
            key={stat.label}
            className="transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
          >
            <div className="flex items-center gap-4">
              <div
                className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${stat.bg} ${stat.color}`}
              >
                <stat.icon className="size-5" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{stat.value}</p>
                <p className="text-xs font-medium text-muted">{stat.label}</p>
              </div>
            </div>
          </Card>
        ))}
      </section>

      <section>
        <Card padding="lg">
          <CardHeader
            title="Activité récente"
            subtitle="Vos derniers contrats traités"
          />
          {isLoading ? (
            <LoadingSpinner label="Chargement de l’activité…" />
          ) : activity && activity.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {activity.map((item) => (
                <DocumentCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted">
              Aucun contrat pour le moment. Déposez votre premier contrat pour
              démarrer.
            </p>
          )}
        </Card>
      </section>
    </div>
  )
}
