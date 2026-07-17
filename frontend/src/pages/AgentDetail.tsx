import { useParams } from 'react-router-dom'
import { Bot, CheckCircle2 } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { Card, CardHeader } from '@/components/ui/Card'
import { agents } from '@/data/mock'
import { cn } from '@/lib/cn'

export function AgentDetailPage() {
  const { id = 'ag1' } = useParams()
  const agent = agents.find((a) => a.id === id) ?? agents[0]

  if (!agent) {
    return (
      <EmptyState
        title="Agent introuvable"
        description="Aucun agent ne correspond à cet identifiant."
      />
    )
  }

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              className="flex size-14 items-center justify-center rounded-2xl text-lg font-bold text-white shadow-md"
              style={{ backgroundColor: agent.color }}
            >
              {agent.initials}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900">{agent.name}</h2>
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide',
                    agent.status === 'active'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-slate-100 text-slate-600',
                  )}
                >
                  <span className="size-1.5 rounded-full bg-current" />
                  {agent.status === 'active' ? 'Actif' : agent.status}
                </span>
              </div>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
                <Bot className="size-4" />
                Agent du pipeline LegalLink
              </p>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card padding="lg">
          <CardHeader title="Description" />
          <p className="text-sm leading-relaxed text-slate-700">
            {agent.description}
          </p>
          <h4 className="mt-6 mb-3 text-sm font-semibold text-slate-900">
            Responsabilités
          </h4>
          <ul className="space-y-2">
            {agent.responsibilities.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-slate-700">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                {item}
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-6">
          <Card padding="lg">
            <CardHeader title="Entrées" />
            <ul className="space-y-2">
              {agent.inputs.map((item) => (
                <li
                  key={item}
                  className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"
                >
                  {item}
                </li>
              ))}
            </ul>
          </Card>
          <Card padding="lg">
            <CardHeader title="Sorties" />
            <ul className="space-y-2">
              {agent.outputs.map((item) => (
                <li
                  key={item}
                  className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand"
                >
                  {item}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Analyses réalisées" value={agent.stats.analyses.toLocaleString('fr-FR')} />
        <StatTile label="Taux de réussite" value={`${agent.stats.successRate}%`} />
        <StatTile label="Temps moyen" value={agent.stats.avgTime} />
        <StatTile label="Coût moyen" value={agent.stats.avgCost} />
      </div>
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <Card className="text-center hover:-translate-y-0.5 transition-transform" padding="lg">
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </Card>
  )
}
