import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { CategoryDonut } from '@/components/charts/CategoryDonut'
import { MonthlyBarChart } from '@/components/charts/MonthlyBarChart'
import { StatSparkline } from '@/components/charts/StatSparkline'
import { DocumentCard } from '@/components/DocumentCard'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { Card, CardHeader } from '@/components/ui/Card'
import {
  analysisCategories,
  dashboardStats,
  monthlyAnalyses,
} from '@/data/mock'
import { useRecentActivity } from '@/hooks/useDocuments'
import { cn } from '@/lib/cn'

export function DashboardPage() {
  const { data: activity, isLoading } = useRecentActivity()

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {dashboardStats.map((stat, index) => (
          <Card
            key={stat.id}
            className="hover:-translate-y-0.5 hover:shadow-md transition-all duration-300"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-muted">{stat.label}</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {stat.value}
                </p>
              </div>
              <StatSparkline
                data={stat.sparkline}
                color={stat.trendUp ? '#22C55E' : '#EF4444'}
              />
            </div>
            <div
              className={cn(
                'mt-3 inline-flex items-center gap-1 text-xs font-medium',
                stat.trendUp ? 'text-success' : 'text-danger',
              )}
            >
              {stat.trendUp ? (
                <ArrowUpRight className="size-3.5" />
              ) : (
                <ArrowDownRight className="size-3.5" />
              )}
              {stat.trend} vs mois dernier
            </div>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3" padding="lg">
          <CardHeader
            title="Activité récente"
            subtitle="Derniers documents traités par le pipeline"
          />
          {isLoading ? (
            <LoadingSpinner label="Chargement de l’activité…" />
          ) : (
            <div className="space-y-3">
              {(activity ?? []).map((item) => (
                <DocumentCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card padding="lg">
            <CardHeader
              title="Répartition des analyses"
              subtitle="Par domaine juridique"
            />
            <CategoryDonut data={analysisCategories} />
          </Card>
          <Card padding="lg">
            <CardHeader
              title="Analyses par mois"
              subtitle="Volume sur 7 mois"
            />
            <MonthlyBarChart data={monthlyAnalyses} />
          </Card>
        </div>
      </section>
    </div>
  )
}
