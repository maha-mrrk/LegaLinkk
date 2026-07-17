import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  Download,
  FileText,
  Share2,
} from 'lucide-react'
import { ScoreGauge } from '@/components/charts/ScoreGauge'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { RiskBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { useAnalysis } from '@/hooks/useDocuments'
import { cn } from '@/lib/cn'

const tabs = [
  'Résumé',
  'Points critiques',
  'Analyse juridique',
  'Analyse financière',
  'Conformité',
  'Recommandations',
]

export function AnalysisPage() {
  const { id = 'd1' } = useParams()
  const { data, isLoading } = useAnalysis(id)
  const [activeTab, setActiveTab] = useState('Points critiques')

  if (isLoading || !data) {
    return <LoadingSpinner label="Chargement de l’analyse…" />
  }

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex size-12 items-center justify-center rounded-xl bg-red-50 text-red-500">
              <FileText className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                {data.document.filename}
              </h2>
              <p className="mt-0.5 text-sm text-muted">
                {data.document.pageCount} pages · {data.document.date}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" leftIcon={<Share2 className="size-4" />}>
              Partager
            </Button>
            <Button leftIcon={<Download className="size-4" />}>Télécharger</Button>
          </div>
        </div>

        <div className="mt-5 flex gap-1 overflow-x-auto border-b border-border pb-px scrollbar-thin">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                'whitespace-nowrap rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === tab
                  ? 'border-b-2 border-brand text-brand'
                  : 'text-muted hover:text-slate-800',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {activeTab === 'Résumé' ? (
            <Card padding="lg">
              <CardHeader title="Résumé exécutif" />
              <p className="text-sm leading-relaxed text-slate-700">
                {data.summary}
              </p>
            </Card>
          ) : null}

          {activeTab === 'Points critiques' ||
          !['Résumé', 'Points critiques'].includes(activeTab) ? (
            <>
              {activeTab !== 'Points critiques' ? (
                <Card padding="lg">
                  <p className="text-sm text-muted">
                    Contenu « {activeTab} » — prêt à être branché sur l’API
                    d’analyse.
                  </p>
                </Card>
              ) : null}
              {activeTab === 'Points critiques'
                ? data.criticalPoints.map((point) => (
                    <Card
                      key={point.id}
                      className="hover:border-brand/20 hover:shadow-md transition-all duration-200"
                      padding="lg"
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg',
                            point.risk === 'high'
                              ? 'bg-red-50 text-danger'
                              : 'bg-amber-50 text-warning',
                          )}
                        >
                          <AlertTriangle className="size-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-slate-900">
                              {point.title}
                            </h3>
                            <RiskBadge risk={point.risk} />
                          </div>
                          <p className="mt-1.5 text-sm text-slate-600">
                            {point.description}
                          </p>
                          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                            <span className="font-medium text-brand">
                              {point.reference}
                            </span>
                            <span className="text-muted">p. {point.page}</span>
                          </div>
                          <button
                            type="button"
                            className="mt-2 text-xs font-medium text-brand hover:underline"
                          >
                            Voir →
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))
                : null}
            </>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card padding="lg">
            <CardHeader title="Score global" />
            <ScoreGauge score={data.score} label={data.riskLabel} />
            <div className="mt-6 grid grid-cols-2 gap-3">
              <Metric label="Conformité" value={`${data.complianceRate}%`} />
              <Metric
                label="Clauses analysées"
                value={String(data.clausesAnalyzed)}
              />
              <Metric
                label="Références juridiques"
                value={String(data.legalReferences)}
                className="col-span-2"
              />
            </div>
          </Card>

          <Card padding="lg">
            <CardHeader title="Agents impliqués" />
            <div className="flex flex-wrap gap-3">
              {data.agents.map((agent) => (
                <Link
                  key={agent.id}
                  to={`/agents/${agent.id}`}
                  className="group flex flex-col items-center gap-1.5"
                >
                  <div
                    className="flex size-11 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm transition group-hover:scale-105"
                    style={{ backgroundColor: agent.color }}
                  >
                    {agent.initials}
                  </div>
                  <span className="text-[11px] text-muted group-hover:text-brand">
                    {agent.name}
                  </span>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Metric({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'rounded-xl bg-slate-50 px-3 py-3 text-center',
        className,
      )}
    >
      <p className="text-lg font-bold text-slate-900">{value}</p>
      <p className="text-[11px] text-muted">{label}</p>
    </div>
  )
}
