import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  HelpCircle,
} from 'lucide-react'
import { ScoreGauge } from '@/components/charts/ScoreGauge'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { RiskBadge } from '@/components/StatusBadge'
import { Card, CardHeader } from '@/components/ui/Card'
import { useDocuments, useLegalAnalysis } from '@/hooks/useDocuments'
import { cn } from '@/lib/cn'
import type { RiskLevel } from '@/types'

const tabs = [
  'Résumé',
  'Points critiques',
  'Informations manquantes',
  'Recommandations',
  'Sources',
]

const RISK_META: Record<RiskLevel, { score: number; label: string }> = {
  low: { score: 85, label: 'Risque faible' },
  medium: { score: 58, label: 'Risque modéré' },
  high: { score: 32, label: 'Risque élevé' },
}

export function AnalysisPage() {
  const { id = '' } = useParams()
  const { data: documents } = useDocuments()
  const { data, isLoading, isError, error } = useLegalAnalysis(id)
  const [activeTab, setActiveTab] = useState('Résumé')

  const document = useMemo(
    () => documents?.find((d) => d.id === id),
    [documents, id],
  )

  const findings = data?.metadata?.risk_findings ?? []
  const risk = data ? RISK_META[data.risk_level] : RISK_META.medium

  if (isLoading) {
    return (
      <LoadingSpinner label="Analyse du contrat en cours… cela peut prendre un instant." />
    )
  }

  if (isError || !data) {
    return (
      <Card padding="lg">
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertTriangle className="size-8 text-danger" />
          <h2 className="text-lg font-semibold text-slate-900">
            Analyse indisponible
          </h2>
          <p className="max-w-md text-sm text-muted">
            {error instanceof Error
              ? error.message
              : "Impossible d'analyser ce contrat pour le moment."}
          </p>
        </div>
      </Card>
    )
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
                {document?.filename ?? 'Contrat'}
              </h2>
              <p className="mt-0.5 text-sm text-muted">
                {document?.pageCount ? `${document.pageCount} pages · ` : ''}
                {document?.date ?? ''}
              </p>
            </div>
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
              <CardHeader title="Analyse juridique" />
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {data.analysis}
              </p>
            </Card>
          ) : null}

          {activeTab === 'Points critiques' ? (
            findings.length ? (
              findings.map((point, index) => (
                <Card
                  key={`${point.category}-${index}`}
                  className="transition-all duration-200 hover:border-brand/20 hover:shadow-md"
                  padding="lg"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg',
                        point.level === 'high'
                          ? 'bg-red-50 text-danger'
                          : point.level === 'medium'
                            ? 'bg-amber-50 text-warning'
                            : 'bg-emerald-50 text-success',
                      )}
                    >
                      <AlertTriangle className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-slate-900">
                          {point.category}
                        </h3>
                        <RiskBadge risk={point.level} />
                      </div>
                      <p className="mt-1.5 text-sm text-slate-600">
                        {point.detail}
                      </p>
                    </div>
                  </div>
                </Card>
              ))
            ) : (
              <EmptyState
                icon={<CheckCircle2 className="size-6 text-success" />}
                text="Aucun point critique majeur détecté."
              />
            )
          ) : null}

          {activeTab === 'Informations manquantes' ? (
            data.missing_information.length ? (
              <Card padding="lg">
                <CardHeader title="Éléments manquants ou ambigus" />
                <ul className="space-y-2.5">
                  {data.missing_information.map((item, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-700">
                      <HelpCircle className="mt-0.5 size-4 shrink-0 text-warning" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState
                icon={<CheckCircle2 className="size-6 text-success" />}
                text="Aucune information manquante identifiée."
              />
            )
          ) : null}

          {activeTab === 'Recommandations' ? (
            data.recommendations.length ? (
              <Card padding="lg">
                <CardHeader title="Recommandations" />
                <ul className="space-y-2.5">
                  {data.recommendations.map((item, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-700">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-brand" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState
                icon={<CheckCircle2 className="size-6 text-success" />}
                text="Aucune recommandation particulière."
              />
            )
          ) : null}

          {activeTab === 'Sources' ? (
            data.sources.length ? (
              <Card padding="lg">
                <CardHeader title="Passages de référence" />
                <div className="space-y-2">
                  {data.sources.map((source, index) => (
                    <div
                      key={source.chunk_id ?? index}
                      className="flex items-center justify-between rounded-lg border border-border bg-slate-50 px-3 py-2.5 text-sm"
                    >
                      <span className="min-w-0 truncate font-medium text-slate-700">
                        {source.filename ?? 'Document'}
                      </span>
                      <span className="ml-3 shrink-0 text-xs text-muted">
                        {source.page ? `p. ${source.page}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            ) : (
              <EmptyState
                icon={<FileText className="size-6 text-muted" />}
                text="Aucune source disponible."
              />
            )
          ) : null}
        </div>

        <div className="space-y-4">
          <Card padding="lg">
            <CardHeader title="Niveau de risque" />
            <ScoreGauge score={risk.score} label={risk.label} />
            <div className="mt-6 grid grid-cols-2 gap-3">
              <Metric label="Points critiques" value={String(findings.length)} />
              <Metric
                label="Passages examinés"
                value={String(data.sources.length)}
              />
              <Metric
                label="Éléments manquants"
                value={String(data.missing_information.length)}
                className="col-span-2"
              />
            </div>
          </Card>

          <Card padding="lg">
            <CardHeader title="Niveau de risque global" />
            <div className="flex items-center justify-center py-2">
              <RiskBadge risk={data.risk_level} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <Card padding="lg">
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        {icon}
        <p className="text-sm text-muted">{text}</p>
      </div>
    </Card>
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
    <div className={cn('rounded-xl bg-slate-50 px-3 py-3 text-center', className)}>
      <p className="text-lg font-bold text-slate-900">{value}</p>
      <p className="text-[11px] text-muted">{label}</p>
    </div>
  )
}
