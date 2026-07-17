import type { ReactNode } from 'react'
import { FileQuestion } from 'lucide-react'
import { cn } from '@/lib/cn'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-white px-6 py-16 text-center',
        className,
      )}
    >
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-brand-soft text-brand">
        {icon ?? <FileQuestion className="size-6" />}
      </div>
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}
