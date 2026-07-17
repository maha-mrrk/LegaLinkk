import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

export function LoadingSpinner({
  className,
  label = 'Chargement…',
}: {
  className?: string
  label?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 text-muted',
        className,
      )}
    >
      <Loader2 className="size-8 animate-spin text-brand" />
      <p className="text-sm">{label}</p>
    </div>
  )
}
