import { useEffect, useRef } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { useDocumentProgress } from '@/hooks/useDocuments'
import type { IngestionStatus } from '@/types'

interface IngestionProgressProps {
  documentId: string
  filename?: string
  onCompleted?: () => void
  onFailed?: () => void
}

interface Step {
  key: string
  label: string
  pct: number
}

/** Ordered, business-friendly milestones (no technical jargon). */
const STEPS: Step[] = [
  { key: 'queued', label: 'Document reçu', pct: 5 },
  { key: 'extracting', label: 'Lecture du contrat', pct: 20 },
  { key: 'cleaning', label: 'Nettoyage du texte', pct: 50 },
  { key: 'chunking', label: 'Organisation du contenu', pct: 65 },
  { key: 'embedding', label: 'Préparation de la recherche', pct: 80 },
  { key: 'indexing', label: 'Finalisation', pct: 95 },
  { key: 'completed', label: 'Prêt pour l’analyse', pct: 100 },
]

/** Friendly, non-technical wording for the live status line. */
const STAGE_MESSAGES: Record<string, string> = {
  queued: 'Votre document est en file d’attente…',
  extracting: 'Lecture de votre contrat…',
  ocr: 'Lecture des pages scannées…',
  cleaning: 'Nettoyage du texte…',
  chunking: 'Organisation du contenu…',
  embedding: 'Préparation de la recherche intelligente…',
  persisting: 'Enregistrement du contenu…',
  indexing: 'Finalisation…',
  completed: 'Votre contrat est prêt à être analysé.',
  failed: 'Le traitement a échoué.',
}

type StepState = 'done' | 'active' | 'pending' | 'error'

function stepStateFor(
  index: number,
  reachedIndex: number,
  status: IngestionStatus,
): StepState {
  if (status === 'completed') return 'done'
  if (index < reachedIndex) return 'done'
  if (index === reachedIndex) return status === 'failed' ? 'error' : 'active'
  return 'pending'
}

function StepIcon({ state }: { state: StepState }) {
  if (state === 'done')
    return <CheckCircle2 className="size-4 text-success" />
  if (state === 'active')
    return <Loader2 className="size-4 animate-spin text-brand" />
  if (state === 'error') return <XCircle className="size-4 text-danger" />
  return <Circle className="size-4 text-slate-300" />
}

export function IngestionProgress({
  documentId,
  filename,
  onCompleted,
  onFailed,
}: IngestionProgressProps) {
  const { data } = useDocumentProgress(documentId)
  const notified = useRef<IngestionStatus | null>(null)

  const status: IngestionStatus = data?.status ?? 'queued'
  const progress = Math.min(100, Math.max(0, data?.progress ?? 0))
  const stageKey = status === 'completed' ? 'completed' : data?.stage ?? 'queued'
  const message =
    status === 'failed'
      ? data?.error || STAGE_MESSAGES.failed
      : STAGE_MESSAGES[stageKey] ?? data?.message ?? 'Traitement en cours…'

  const reachedIndex = STEPS.reduce(
    (acc, step, i) => (progress >= step.pct ? i : acc),
    0,
  )

  useEffect(() => {
    if (status === 'completed' && notified.current !== 'completed') {
      notified.current = 'completed'
      onCompleted?.()
    }
    if (status === 'failed' && notified.current !== 'failed') {
      notified.current = 'failed'
      onFailed?.()
    }
  }, [status, onCompleted, onFailed])

  const barColor =
    status === 'failed'
      ? 'bg-danger'
      : status === 'completed'
        ? 'bg-success'
        : 'bg-brand'

  return (
    <div
      className={cn(
        'mt-4 rounded-xl border p-4 transition-colors',
        status === 'failed'
          ? 'border-red-200 bg-red-50/60'
          : status === 'completed'
            ? 'border-green-200 bg-green-50/60'
            : 'border-brand/20 bg-brand-soft/40',
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'flex size-9 items-center justify-center rounded-lg',
            status === 'completed'
              ? 'bg-green-100 text-success'
              : status === 'failed'
                ? 'bg-red-100 text-danger'
                : 'bg-white text-brand shadow-sm',
          )}
        >
          {status === 'completed' ? (
            <Sparkles className="size-4" />
          ) : status === 'failed' ? (
            <AlertTriangle className="size-4" />
          ) : (
            <FileText className="size-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          {filename ? (
            <p className="truncate text-sm font-medium text-slate-900">
              {filename}
            </p>
          ) : null}
          <p
            className={cn(
              'truncate text-xs',
              status === 'failed'
                ? 'text-danger'
                : status === 'completed'
                  ? 'text-success'
                  : 'text-brand',
            )}
          >
            {message}
          </p>
        </div>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-700">
          {progress}%
        </span>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200/70">
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor)}
          style={{ width: `${progress}%` }}
        />
      </div>

      <ul className="mt-4 space-y-2">
        {STEPS.map((step, index) => {
          const state = stepStateFor(index, reachedIndex, status)
          return (
            <li key={step.key} className="flex items-center gap-2.5 text-sm">
              <StepIcon state={state} />
              <span
                className={cn(
                  state === 'done' && 'text-slate-600',
                  state === 'active' && 'font-medium text-slate-900',
                  state === 'error' && 'font-medium text-danger',
                  state === 'pending' && 'text-slate-400',
                )}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
