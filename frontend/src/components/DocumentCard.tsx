import { FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import { Card } from '@/components/ui/Card'
import type { ActivityItem } from '@/types'

export function DocumentCard({ item }: { item: ActivityItem }) {
  return (
    <Link to={`/analysis/d1`} className="block">
      <Card
        padding="sm"
        className="group flex items-start gap-3 hover:shadow-md hover:border-brand/20 transition-all duration-200"
      >
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-500">
          <FileText className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="truncate text-sm font-medium text-slate-900 group-hover:text-brand transition-colors">
              {item.title}
            </p>
            <StatusBadge status={item.status} />
          </div>
          <p className="mt-0.5 truncate text-xs text-muted">{item.subtitle}</p>
          <p className="mt-1 text-[11px] text-slate-400">{item.timeAgo}</p>
        </div>
      </Card>
    </Link>
  )
}
