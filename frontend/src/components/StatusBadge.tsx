import { cn } from '@/lib/cn'
import type { DocumentStatus, RiskLevel } from '@/types'

const statusStyles: Record<DocumentStatus, string> = {
  completed: 'bg-green-50 text-green-700 ring-green-200',
  processing: 'bg-blue-50 text-blue-700 ring-blue-200',
  queued: 'bg-amber-50 text-amber-700 ring-amber-200',
  pending: 'bg-slate-100 text-slate-600 ring-slate-200',
  failed: 'bg-red-50 text-red-700 ring-red-200',
}

const statusLabels: Record<DocumentStatus, string> = {
  completed: 'Terminé',
  processing: 'En cours',
  queued: 'En file',
  pending: 'En attente',
  failed: 'Échec',
}

const riskStyles: Record<RiskLevel, string> = {
  high: 'bg-red-50 text-red-700 ring-red-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-green-50 text-green-700 ring-green-200',
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
          status === 'processing' && 'bg-brand animate-pulse',
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
