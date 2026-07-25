import { cn } from '@/lib/cn'
import type { DocumentStatus, RiskLevel } from '@/types'

const statusStyles: Record<DocumentStatus, string> = {
  completed: 'bg-success-soft text-success ring-success/30',
  processing: 'bg-primary-soft text-primary ring-primary/30',
  queued: 'bg-warning-soft text-amber-700 ring-amber-300/60',
  pending: 'bg-slate-100 text-slate-600 ring-slate-200',
  failed: 'bg-danger-soft text-danger ring-danger/30',
}

const statusLabels: Record<DocumentStatus, string> = {
  completed: 'Terminé',
  processing: 'En cours',
  queued: 'En file',
  pending: 'En attente',
  failed: 'Échec',
}

const riskStyles: Record<RiskLevel, string> = {
  high: 'bg-danger-soft text-danger ring-danger/30',
  medium: 'bg-warning-soft text-amber-700 ring-amber-300/60',
  low: 'bg-success-soft text-success ring-success/30',
}

const riskLabels: Record<RiskLevel, string> = {
  high: 'Risque élevé',
  medium: 'Risque moyen',
  low: 'Risque faible',
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
        statusStyles[status],
      )}
    >
      <span
        className={cn(
          'size-1.5 rounded-full',
          status === 'completed' && 'bg-success',
          status === 'processing' && 'bg-primary animate-pulse',
          status === 'queued' && 'bg-warning',
          status === 'pending' && 'bg-slate-400',
          status === 'failed' && 'bg-danger',
        )}
      />
      {statusLabels[status]}
    </span>
  )
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset',
        riskStyles[risk],
      )}
    >
      {riskLabels[risk]}
    </span>
  )
}
