import { Check, CircleDot, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { pipelineRun } from '@/data/mock'
import { cn } from '@/lib/cn'
import type { PipelineStageStatus } from '@/types'

export function SupervisionPage() {
  const run = pipelineRun

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              {run.documentName}
            </h2>
            <p className="text-sm text-muted">Pipeline d’analyse en temps réel</p>
          </div>
          <div className="text-right">
            <p className="text-xs font-medium text-muted">Progression globale</p>
            <p className="text-lg font-bold text-brand">{run.progress}%</p>
          </div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-brand transition-all duration-700"
            style={{ width: `${run.progress}%` }}
          />
        </div>
      </Card>

      <Card padding="lg" className="overflow-x-auto">
        <CardHeader title="Pipeline" subtitle="Étapes du traitement documentaire" />
        <div className="flex min-w-max items-center gap-2 pb-2">
          {run.stages.map((stage, index) => (
            <div key={stage.id} className="flex items-center gap-2">
              <StageNode label={stage.label} status={stage.status} />
              {index < run.stages.length - 1 ? (
                <div
                  className={cn(
                    'h-0.5 w-6 rounded-full',
                    stage.status === 'done' ? 'bg-brand' : 'bg-slate-200',
                  )}
                />
              ) : null}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card padding="lg">
          <CardHeader title="Étape en cours" />
          <p className="text-sm font-semibold text-brand">{run.activeStageLabel}</p>
          <p className="mt-2 text-sm text-slate-600">{run.activeStageDetail}</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-brand" />
          </div>
          <p className="mt-2 text-xs text-muted">Récupération des chunks pertinents…</p>
        </Card>

        <Card padding="lg" className="lg:col-span-1">
          <CardHeader title="Timeline des événements" />
          <ul className="max-h-72 space-y-3 overflow-y-auto pr-1 scrollbar-thin">
            {run.events.map((event) => (
              <li key={event.id} className="flex gap-3 text-sm">
                <span
                  className={cn(
                    'mt-1.5 size-2 shrink-0 rounded-full',
                    event.status === 'ok' && 'bg-success',
                    event.status === 'info' && 'bg-brand',
                    event.status === 'warn' && 'bg-warning',
                  )}
                />
                <div>
                  <p className="text-[11px] font-medium text-slate-400">
                    {event.time}
                  </p>
                  <p className="text-slate-700">{event.message}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card padding="lg">
          <CardHeader title="Consommation IA" />
          <div className="space-y-3 text-sm">
            <Row label="Modèle" value={run.consumption.model} />
            <Row
              label="Tokens entrée"
              value={run.consumption.inputTokens.toLocaleString('fr-FR')}
            />
            <Row
              label="Tokens sortie"
              value={run.consumption.outputTokens.toLocaleString('fr-FR')}
            />
            <div className="rounded-xl bg-brand-soft px-4 py-3">
              <p className="text-xs text-brand">Coût estimé</p>
              <p className="text-xl font-bold text-brand">
                {run.consumption.estimatedCost}
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

function StageNode({
  label,
  status,
}: {
  label: string
  status: PipelineStageStatus
}) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={cn(
          'flex size-10 items-center justify-center rounded-full border-2 transition-all',
          status === 'done' && 'border-brand bg-brand text-white',
          status === 'active' &&
            'border-brand bg-brand-soft text-brand shadow-[0_0_0_4px_rgba(37,99,235,0.15)] animate-pulse',
          status === 'pending' && 'border-slate-200 bg-white text-slate-400',
          status === 'error' && 'border-danger bg-red-50 text-danger',
        )}
      >
        {status === 'done' ? (
          <Check className="size-4" />
        ) : status === 'active' ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <CircleDot className="size-4" />
        )}
      </div>
      <span
        className={cn(
          'text-[11px] font-medium',
          status === 'active' ? 'text-brand' : 'text-muted',
        )}
      >
        {label}
      </span>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-2 last:border-0">
      <span className="text-muted">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  )
}
