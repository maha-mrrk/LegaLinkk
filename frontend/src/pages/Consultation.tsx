import { useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  Coins,
  Download,
  FileOutput,
  FileText,
  Gavel,
  Layers,
  Library,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  Printer,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  type LucideIcon,
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { MarkdownText } from '@/components/MarkdownText'
import { UploadZone } from '@/components/UploadZone'
import { IngestionProgress } from '@/components/IngestionProgress'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { suggestions } from '@/data/mock'
import { useDocuments, useUploadDocument } from '@/hooks/useDocuments'
import {
  createBackgroundChatJob,
  downloadDocumentPdf,
  generateDocument,
  streamBackgroundChatJob,
  wantsDocument,
} from '@/services/chat'
import { fetchDocumentBlob } from '@/services/documents'
import { fetchGeneratedDocumentBlob } from '@/services/generatedDocuments'
import { useConversations } from '@/hooks/useConversations'
import { cn } from '@/lib/cn'
import type {
  AgentDomain,
  ChatAgentAnalysis,
  ChatMessage,
  ChatMessageSource,
  ChatSourceRef,
} from '@/types'

/** Open a source document's PDF in a new tab (authenticated blob fetch). */
async function openDocument(documentId: string): Promise<void> {
  const blob = await fetchDocumentBlob(documentId)
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

/** Dedupe API source refs (by filename) into clickable message sources. */
function toMessageSources(refs: ChatSourceRef[]): ChatMessageSource[] {
  const seen = new Set<string>()
  const out: ChatMessageSource[] = []
  for (const ref of refs) {
    const filename = ref.filename
    if (!filename || seen.has(filename)) continue
    seen.add(filename)
    out.push({ filename, documentId: ref.document_id })
  }
  return out
}

/** Per-domain presentation (label + icon + soft badge colors). */
const DOMAIN_STYLE: Record<
  AgentDomain,
  { label: string; icon: LucideIcon; badge: string }
> = {
  legal: {
    label: 'Agent Juridique',
    icon: Gavel,
    badge: 'bg-primary-soft text-primary',
  },
  finance: {
    label: 'Agent Financier',
    icon: Coins,
    badge: 'bg-warning-soft text-warning',
  },
  compliance: {
    label: 'Agent Conformité',
    icon: ShieldCheck,
    badge: 'bg-success-soft text-success',
  },
}

interface SlashCommand {
  key: string
  command: string
  label: string
  desc: string
  icon: LucideIcon
}

/** The four slash options shown when the user types "/" in the composer. */
const SLASH_COMMANDS: SlashCommand[] = [
  {
    key: 'legal',
    command: '/legal',
    label: 'Agent Juridique',
    desc: 'Clauses, obligations et risques contractuels',
    icon: Gavel,
  },
  {
    key: 'finance',
    command: '/finance',
    label: 'Agent Financier',
    desc: 'Paiements, pénalités, coûts et exposition',
    icon: Coins,
  },
  {
    key: 'compliance',
    command: '/compliance',
    label: 'Agent Conformité',
    desc: 'RGPD, réglementation, audit et conformité',
    icon: ShieldCheck,
  },
  {
    key: 'synthese',
    command: '/synthese',
    label: 'Synthèse des 3 agents',
    desc: 'Analyse croisée et recommandation globale',
    icon: Layers,
  },
]

type AgentCommand =
  | { mode: 'single'; domain: AgentDomain; label: string; toSend: string }
  | { mode: 'multi'; label: string; toSend: string }

/**
 * Parse a leading slash command from the composer text.
 * - `/legal|/finance|/compliance …` → single agent (prefix kept so the backend
 *   routes it).
 * - `/synthese|/synth|/tous|/all …` → multi-agent synthesis (prefix stripped so
 *   the backend runs all three + synthesis).
 * Returns `null` for a normal message (handled by the streaming chat).
 */
function parseAgentCommand(text: string): AgentCommand | null {
  const match = /^\/([\p{L}]+)\b([\s\S]*)$/u.exec(text.trim())
  if (!match) return null
  const cmd = match[1].toLowerCase()
  const rest = match[2].trim()
  if (cmd === 'legal' || cmd === 'finance' || cmd === 'compliance') {
    return {
      mode: 'single',
      domain: cmd,
      label: DOMAIN_STYLE[cmd].label,
      toSend: rest ? `/${cmd} ${rest}` : `/${cmd}`,
    }
  }
  if (['synthese', 'synthèse', 'synth', 'tous', 'all'].includes(cmd)) {
    return {
      mode: 'multi',
      label: 'Synthèse des 3 agents',
      toSend: rest || 'Analyse ce contrat en détail.',
    }
  }
  return null
}

/** Open the generated HTML in a new tab and trigger the browser print → PDF. */
function printDocument(html: string): void {
  const win = window.open('', '_blank', 'noopener,noreferrer')
  if (!win) return
  win.document.open()
  win.document.write(html)
  win.document.close()
  win.focus()
  // Give the new document a moment to lay out before printing.
  win.setTimeout(() => win.print(), 400)
}

/** Download the generated HTML document as a standalone .html file. */
function downloadDocument(html: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `document-legallink-${Date.now()}.html`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function DocumentCard({
  html,
  sourceDocumentId,
  question,
  generatedDocumentId,
}: {
  html: string
  sourceDocumentId?: string
  question?: string
  generatedDocumentId?: string
}) {
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  const handleDownloadPdf = async () => {
    setPdfError(null)
    setPdfLoading(true)
    try {
      const title = question
        ? `Rapport — ${question.slice(0, 100)}`
        : 'Document généré dans une consultation'
      const filename = `document-legallink-${Date.now()}.pdf`
      const blob = generatedDocumentId
        ? await fetchGeneratedDocumentBlob(generatedDocumentId)
        : await downloadDocumentPdf(html, {
            filename,
            title,
            sourceDocumentId,
            kind: 'chat_report',
            question,
          })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch {
      setPdfError('Le téléchargement du PDF a échoué. Veuillez réessayer.')
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-border bg-slate-50">
      <div className="flex items-center justify-between gap-2 border-b border-border bg-white px-3 py-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-slate-600">
          <FileText className="size-3.5 text-brand" />
          Document généré
        </span>
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={pdfLoading}
            className="inline-flex items-center gap-1 rounded-lg bg-brand px-2.5 py-1 text-[11px] font-medium text-white transition hover:bg-brand-dark disabled:opacity-60"
          >
            {pdfLoading ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Download className="size-3" />
            )}
            {pdfLoading ? 'Génération…' : 'Télécharger PDF'}
          </button>
          <button
            type="button"
            onClick={() => printDocument(html)}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-brand/40 hover:text-brand"
          >
            <Printer className="size-3" /> Imprimer
          </button>
          <button
            type="button"
            onClick={() => downloadDocument(html)}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-brand/40 hover:text-brand"
          >
            <FileText className="size-3" /> HTML
          </button>
        </div>
      </div>
      {pdfError ? (
        <p className="border-b border-border bg-danger/5 px-3 py-1.5 text-[11px] text-danger">
          {pdfError}
        </p>
      ) : null}
      <iframe
        // Sandbox with no allowances: renders styled HTML but blocks scripts.
        sandbox=""
        srcDoc={html}
        title="Aperçu du document généré"
        className="h-80 w-full bg-white"
      />
    </div>
  )
}

const THINKING_STEPS = [
  'Recherche dans vos documents…',
  'Analyse des clauses pertinentes…',
  'Vérification des références…',
  'Rédaction de la réponse…',
]

function nowLabel(): string {
  return new Date().toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatElapsed(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return ''
  if (seconds < 60) return `${seconds.toFixed(1).replace('.', ',')} s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m} min ${s.toString().padStart(2, '0')} s`
}

function todayHeader(): string {
  const label = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

/** A fresh assistant greeting for a brand-new conversation. */
function welcomeMessage(): ChatMessage {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      'Bonjour. Déposez un contrat ou posez une question juridique — je peux résumer, détecter les risques et citer les références applicables.',
    timestamp: nowLabel(),
  }
}

/** Conversation title = the first question asked (truncated). */
function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === 'user')
  const text = firstUser?.content.trim() || 'Nouvelle conversation'
  return text.length > 48 ? `${text.slice(0, 48)}…` : text
}

/** Short, human relative time for the history list (e.g. "il y a 3 min"). */
function relativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const min = Math.floor(diff / 60_000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `il y a ${min} min`
  const hours = Math.floor(min / 60)
  if (hours < 24) return `il y a ${hours} h`
  const days = Math.floor(hours / 24)
  if (days < 7) return `il y a ${days} j`
  return new Date(timestamp).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  })
}

function Avatar({ role }: { role: ChatMessage['role'] }) {
  if (role === 'user') {
    return (
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
        <User className="size-4" />
      </div>
    )
  }
  return (
    <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand-dark text-white shadow-sm">
      <Logo className="size-5" />
    </div>
  )
}

function SourceChips({
  sources,
  isUser = false,
}: {
  sources: ChatMessageSource[]
  isUser?: boolean
}) {
  const [openingId, setOpeningId] = useState<string | null>(null)
  const [openError, setOpenError] = useState(false)

  const handleOpenSource = async (documentId: string) => {
    setOpenError(false)
    setOpeningId(documentId)
    try {
      await openDocument(documentId)
    } catch {
      setOpenError(true)
    } finally {
      setOpeningId(null)
    }
  }

  if (!sources.length) return null

  return (
    <>
      <div
        className={cn(
          'mt-2.5 flex flex-wrap gap-1.5 border-t pt-2',
          isUser ? 'border-white/20' : 'border-black/10',
        )}
      >
        {sources.map((src) => (
          <button
            key={src.filename}
            type="button"
            onClick={() => src.documentId && handleOpenSource(src.documentId)}
            disabled={!src.documentId || openingId === src.documentId}
            title={
              src.documentId
                ? 'Ouvrir le document (PDF)'
                : 'Document indisponible'
            }
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium transition',
              isUser
                ? 'bg-white/15 text-white hover:bg-white/25'
                : 'bg-primary-soft text-primary hover:bg-primary/15',
              src.documentId ? 'cursor-pointer' : 'cursor-default opacity-70',
            )}
          >
            {openingId === src.documentId ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <FileText className="size-3" />
            )}
            {src.filename}
          </button>
        ))}
      </div>
      {openError ? (
        <p className="mt-1.5 text-[11px] text-danger">
          Impossible d’ouvrir le document.
        </p>
      ) : null}
    </>
  )
}

/** Collapsible per-agent analyses shown under a multi-agent synthesis. */
function AgentAnalysisList({ analyses }: { analyses: ChatAgentAnalysis[] }) {
  if (!analyses.length) return null
  return (
    <div className="mt-3 space-y-2 border-t border-black/10 pt-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        Analyses détaillées des agents
      </p>
      {analyses.map((analysis) => {
        const style = DOMAIN_STYLE[analysis.domain as AgentDomain]
        const Icon = style?.icon ?? Sparkles
        return (
          <details
            key={analysis.domain || analysis.label}
            className="group rounded-xl border border-border bg-slate-50/70"
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2">
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                  style?.badge ?? 'bg-slate-200 text-slate-600',
                )}
              >
                <Icon className="size-3" />
                {analysis.label}
              </span>
              {analysis.status !== 'ok' ? (
                <span className="text-[10px] font-medium text-danger">
                  indisponible
                </span>
              ) : null}
              <ChevronDown className="ml-auto size-4 text-slate-400 transition group-open:rotate-180" />
            </summary>
            <div className="border-t border-border px-3 py-2.5 text-sm text-slate-700">
              <MarkdownText content={analysis.answer} />
              <SourceChips sources={analysis.sources ?? []} />
            </div>
          </details>
        )
      })}
    </div>
  )
}

function MessageRow({
  message,
  streaming = false,
  liveSeconds,
}: {
  message: ChatMessage
  streaming?: boolean
  liveSeconds?: number
}) {
  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        'flex animate-message-in items-end gap-2.5',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <Avatar role={message.role} />
      <div className={cn('flex max-w-[80%] flex-col', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm shadow-sm',
            isUser
              ? 'rounded-br-md bg-brand text-white'
              : 'rounded-bl-md bg-white ring-1 ring-border text-slate-800',
          )}
        >
          {isUser ? (
            <p className="leading-relaxed whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <div className="text-sm">
              {message.agentLabel ? (
                <div className="mb-1.5 inline-flex items-center gap-1 rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-semibold text-primary">
                  <Sparkles className="size-3" />
                  {message.agentLabel}
                </div>
              ) : null}
              <MarkdownText content={message.content} />
              {streaming ? (
                <span className="ml-0.5 inline-block h-3.5 w-[3px] translate-y-0.5 animate-pulse rounded-sm bg-brand align-middle" />
              ) : null}
            </div>
          )}
          {message.document ? (
            <DocumentCard
              html={message.document}
              sourceDocumentId={message.generatedReportSourceDocumentId}
              question={message.generatedReportQuestion}
              generatedDocumentId={message.generatedDocumentId}
            />
          ) : null}
          {message.agentAnalyses?.length ? (
            <AgentAnalysisList analyses={message.agentAnalyses} />
          ) : null}
          <SourceChips sources={message.sources ?? []} isUser={isUser} />
        </div>
        <span className="mt-1 px-1 text-[10px] text-slate-400">
          {message.timestamp}
          {streaming && liveSeconds != null ? (
            <span className="text-brand"> · {formatElapsed(liveSeconds)}</span>
          ) : message.role === 'assistant' && message.elapsed != null ? (
            <span> · Généré en {formatElapsed(message.elapsed)}</span>
          ) : null}
        </span>
      </div>
    </div>
  )
}

function ThinkingBubble({
  step,
  seconds,
}: {
  step: number
  seconds?: number
}) {
  return (
    <div className="flex animate-message-in items-end gap-2.5">
      <Avatar role="assistant" />
      <div className="flex flex-col">
        <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm ring-1 ring-border">
          <span className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1.5 rounded-full bg-brand"
                style={{
                  animation: 'typing-bounce 1.2s infinite ease-in-out',
                  animationDelay: `${i * 0.18}s`,
                }}
              />
            ))}
          </span>
          <span className="text-xs font-medium text-slate-500">
            {THINKING_STEPS[step]}
          </span>
          {seconds != null && seconds >= 0.3 ? (
            <span className="text-[11px] font-medium tabular-nums text-brand">
              {formatElapsed(seconds)}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function ConsultationPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    welcomeMessage(),
  ])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [selectedDocId, setSelectedDocId] = useState('')
  const [chatMode, setChatMode] = useState<'conversation' | 'generation'>(
    'conversation',
  )
  const [sending, setSending] = useState(false)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [thinkingStep, setThinkingStep] = useState(0)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [activeUpload, setActiveUpload] = useState<{
    documentId: string
    filename: string
  } | null>(null)
  const [attachError, setAttachError] = useState<string | null>(null)
  // Slash-command menu (agent picker) state.
  const [slashIndex, setSlashIndex] = useState(0)
  const [slashClosed, setSlashClosed] = useState(false)
  const upload = useUploadDocument()
  const { data: documents } = useDocuments()
  const { conversations, upsert, remove } = useConversations()
  const scrollRef = useRef<HTMLDivElement>(null)
  const startRef = useRef<number>(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const resumingJobsRef = useRef(new Set<string>())
  // Whether we already auto-scoped the chat to the current attachment.
  const autoScopedRef = useRef(false)

  // Only indexed documents can be searched; the empty value means "all".
  const searchableDocs = (documents ?? []).filter((d) => d.indexed)
  const selectedDoc = searchableDocs.find((d) => d.id === selectedDocId)
  const scopeLabel = selectedDoc
    ? selectedDoc.filename
    : 'Toute la bibliothèque'
  const uploadReady =
    !!activeUpload &&
    searchableDocs.some((d) => d.id === activeUpload.documentId)

  const MAX_UPLOAD_BYTES = 25 * 1024 * 1024

  const attachFile = (file: File | undefined) => {
    if (!file || sending || upload.isPending) return
    setAttachError(null)
    const isPdf =
      file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      setAttachError('Format non pris en charge : seuls les PDF sont acceptés.')
      return
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setAttachError('Fichier trop volumineux (25 Mo maximum).')
      return
    }
    autoScopedRef.current = false
    upload.mutate(file, {
      onSuccess: (result) => {
        setActiveUpload({
          documentId: result.documentId,
          filename: result.filename,
        })
      },
      onError: (err) => {
        setAttachError(
          err instanceof Error
            ? err.message
            : "L'envoi du fichier a échoué. Veuillez réessayer.",
        )
      },
    })
  }

  const handleAttachClick = () => {
    if (sending || upload.isPending) return
    fileInputRef.current?.click()
  }

  // Once the freshly attached file is indexed, scope the chat to it so the
  // next questions target that document by default.
  useEffect(() => {
    if (!activeUpload || autoScopedRef.current) return
    if (searchableDocs.some((d) => d.id === activeUpload.documentId)) {
      setSelectedDocId(activeUpload.documentId)
      autoScopedRef.current = true
    }
  }, [searchableDocs, activeUpload])

  // Persist the active conversation whenever it changes (once it has a real
  // question). New conversations get an id lazily in `send`.
  useEffect(() => {
    if (!activeId) return
    if (!messages.some((m) => m.role === 'user')) return
    const existing = conversations.find((c) => c.id === activeId)
    upsert({
      id: activeId,
      title: deriveTitle(messages),
      messages,
      createdAt: existing?.createdAt ?? Date.now(),
      updatedAt: Date.now(),
    })
    // `conversations`/`upsert` are intentionally excluded to avoid a save loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, activeId])

  const startNewConversation = () => {
    if (sending) return
    setActiveId(null)
    setMessages([welcomeMessage()])
    setDraft('')
  }

  const openConversation = (id: string) => {
    if (sending || id === activeId) return
    const conversation = conversations.find((c) => c.id === id)
    if (!conversation) return
    setActiveId(id)
    setMessages(
      conversation.messages.length ? conversation.messages : [welcomeMessage()],
    )
  }

  const deleteConversation = (id: string) => {
    remove(id)
    if (id === activeId) startNewConversation()
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, sending, thinkingStep])

  useEffect(() => {
    if (!sending) {
      setThinkingStep(0)
      return
    }
    const id = setInterval(() => {
      setThinkingStep((s) => Math.min(s + 1, THINKING_STEPS.length - 1))
    }, 3500)
    return () => clearInterval(id)
  }, [sending])

  // Live elapsed timer while the assistant is thinking / streaming.
  useEffect(() => {
    if (!sending) return
    const start = performance.now()
    setElapsedMs(0)
    const id = setInterval(() => setElapsedMs(performance.now() - start), 100)
    return () => clearInterval(id)
  }, [sending])

  // Reconnect to any unfinished Redis-backed response when a saved
  // conversation is reopened after navigation or a browser refresh.
  useEffect(() => {
    if (sending) return
    const pending = messages.find(
      (message) =>
        message.role === 'assistant' &&
        message.backgroundJobId &&
        message.backgroundJobStatus === 'processing',
    )
    if (!pending?.backgroundJobId) return
    if (resumingJobsRef.current.has(pending.backgroundJobId)) return

    const jobId = pending.backgroundJobId
    const assistantId = pending.id
    resumingJobsRef.current.add(jobId)
    setSending(true)
    setStreamingId(assistantId)
    setMessages((prev) =>
      prev.map((message) =>
        message.id === assistantId
          ? {
              ...message,
              content: '',
              sources: [],
              agentAnalyses: undefined,
            }
          : message,
      ),
    )

    let restoredSources: ChatMessageSource[] = []
    void streamBackgroundChatJob(jobId, {
      onAgent: ({ domain, label }) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  agentLabel:
                    DOMAIN_STYLE[domain as AgentDomain]?.label ??
                    label ??
                    message.agentLabel,
                }
              : message,
          ),
        )
      },
      onSources: (incoming) => {
        restoredSources = toMessageSources(incoming)
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, sources: restoredSources }
              : message,
          ),
        )
      },
      onAnalyses: (list) => {
        const analyses: ChatAgentAnalysis[] = list.map((analysis) => ({
          domain: analysis.domain ?? '',
          label:
            DOMAIN_STYLE[analysis.domain as AgentDomain]?.label ?? analysis.label,
          status: analysis.status,
          answer:
            analysis.answer || analysis.message || 'Analyse indisponible.',
          sources: toMessageSources(analysis.sources ?? []),
        }))
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, agentAnalyses: analyses }
              : message,
          ),
        )
      },
      onDelta: (text) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, content: message.content + text }
              : message,
          ),
        )
      },
      onDone: ({ answer, metadata }) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: message.content || answer || '',
                  sources: restoredSources.length
                    ? restoredSources
                    : message.sources,
                  elapsed:
                    typeof metadata.generation_time === 'number'
                      ? metadata.generation_time
                      : message.elapsed,
                  backgroundJobStatus: 'completed',
                }
              : message,
          ),
        )
      },
      onError: (message) => {
        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantId
              ? {
                  ...item,
                  content:
                    item.content ||
                    `Désolé, la génération a échoué : ${message}`,
                  backgroundJobStatus: 'failed',
                }
              : item,
          ),
        )
      },
    }).finally(() => {
      resumingJobsRef.current.delete(jobId)
      setStreamingId(null)
      setSending(false)
    })
    // The Set prevents duplicate followers while replayed fragments update messages.
  }, [messages, sending])

  const send = async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || sending) return

    // First message of a fresh chat → open a new persisted conversation.
    if (!activeId) setActiveId(crypto.randomUUID())

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        timestamp: nowLabel(),
      },
    ])
    setDraft('')
    setSending(true)
    startRef.current = performance.now()

    const assistantId = crypto.randomUUID()
    let started = false
    let sources: ChatMessageSource[] = []

    const measuredElapsed = () =>
      Math.round(((performance.now() - startRef.current) / 1000) * 10) / 10

    // Conversation mode never creates files implicitly. If the user asks for
    // one, guide them to the explicit generation mode instead.
    if (chatMode === 'conversation' && wantsDocument(trimmed)) {
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content:
            'Cette demande nécessite le mode **Génération PDF**. Sélectionnez ce mode au-dessus de la zone de saisie, puis renvoyez votre demande. Aucun document n’a été créé.',
          timestamp: nowLabel(),
        },
      ])
      setSending(false)
      return
    }

    // Agent mode: the message starts with a slash command (/legal, /finance,
    // /compliance → one agent; /synthese → all three + streamed synthesis).
    // Streamed (fragmented) exactly like the normal chat, via /agents/stream.
    const agentCmd = parseAgentCommand(trimmed)
    if (agentCmd) {
      let agentLabel: string | undefined =
        agentCmd.mode === 'single' ? agentCmd.label : undefined
      let agentAnalyses: ChatAgentAnalysis[] | undefined
      let agentSources: ChatMessageSource[] = []

      // Create-or-update the single assistant message for this run.
      const upsertAssistant = (patch: Partial<ChatMessage>) => {
        setMessages((prev) => {
          if (prev.some((m) => m.id === assistantId)) {
            return prev.map((m) =>
              m.id === assistantId ? { ...m, ...patch } : m,
            )
          }
          return [
            ...prev,
            {
              id: assistantId,
              role: 'assistant',
              content: '',
              timestamp: nowLabel(),
              agentLabel,
              agentAnalyses,
              sources: agentSources,
              ...patch,
            },
          ]
        })
      }

      let job
      try {
        job = await createBackgroundChatJob(agentCmd.toSend, {
          mode: 'agent',
          topK: 15,
          finalK: 5,
          documentId: selectedDocId || null,
        })
      } catch (error) {
        upsertAssistant({
          content: `Désolé, la réponse n’a pas pu être démarrée : ${
            error instanceof Error ? error.message : 'service indisponible'
          }`,
        })
        setSending(false)
        return
      }
      started = true
      setStreamingId(assistantId)
      upsertAssistant({
        backgroundJobId: job.jobId,
        backgroundJobMode: 'agent',
        backgroundJobStatus: 'processing',
      })

      await streamBackgroundChatJob(
        job.jobId,
        {
          onAgent: ({ mode, domain, label }) => {
            if (mode === 'single') {
              agentLabel =
                DOMAIN_STYLE[domain as AgentDomain]?.label ??
                label ??
                agentCmd.label
            }
          },
          onSources: (incoming) => {
            agentSources = toMessageSources(incoming)
            if (started) upsertAssistant({ sources: agentSources })
          },
          onAnalyses: (list) => {
            agentAnalyses = list.map((a) => ({
              domain: a.domain ?? '',
              label: DOMAIN_STYLE[a.domain as AgentDomain]?.label ?? a.label,
              status: a.status,
              answer: a.answer || a.message || 'Analyse indisponible.',
              sources: toMessageSources(a.sources ?? []),
            }))
            started = true
            setStreamingId(assistantId)
            upsertAssistant({ agentAnalyses })
          },
          onDelta: (text) => {
            if (!started) {
              started = true
              setStreamingId(assistantId)
              upsertAssistant({ content: text })
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + text }
                    : m,
                ),
              )
            }
          },
          onDone: ({ answer, metadata }) => {
            const elapsed =
              typeof metadata.generation_time === 'number'
                ? (metadata.generation_time as number)
                : measuredElapsed()
            if (!started && answer) {
              started = true
              upsertAssistant({ content: answer, elapsed })
              return
            }
            upsertAssistant({
              elapsed,
              sources: agentSources,
              agentAnalyses,
              backgroundJobStatus: 'completed',
            })
          },
          onError: (msg) => {
            if (!started) {
              setMessages((prev) => [
                ...prev,
                {
                  id: assistantId,
                  role: 'assistant',
                  content: `Désolé, l’interrogation des agents a échoué : ${msg}`,
                  timestamp: nowLabel(),
                },
              ])
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: `${m.content}\n\n[Interrompu : ${msg}]`,
                        backgroundJobStatus: 'failed',
                      }
                    : m,
                ),
              )
            }
          },
        },
      )

      setStreamingId(null)
      setSending(false)
      return
    }

    // Generation mode: every request becomes a persisted, branded PDF.
    if (chatMode === 'generation') {
      try {
        const result = await generateDocument(trimmed, {
          topK: 15,
          finalK: 5,
          documentId: selectedDocId || null,
        })
        const docSources = toMessageSources(result.sources)
        const sourceIds = Array.from(
          new Set(result.sources.map((source) => source.document_id).filter(Boolean)),
        )
        const reportSourceDocumentId =
          selectedDocId || (sourceIds.length === 1 ? sourceIds[0] : undefined)
        const elapsed =
          typeof result.metadata?.generation_time === 'number'
            ? (result.metadata.generation_time as number)
            : measuredElapsed()
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: 'assistant',
            content:
              'Voici le document généré à partir de vos documents. Vous pouvez l’imprimer en PDF ou le télécharger.',
            document: result.html,
            generatedReportSourceDocumentId: reportSourceDocumentId,
            generatedReportQuestion: trimmed,
            generatedDocumentId: result.generated_document_id,
            sources: docSources,
            timestamp: nowLabel(),
            elapsed,
          },
        ])
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'La génération a échoué.'
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: 'assistant',
            content: `Désolé, la génération du document a échoué : ${msg}`,
            timestamp: nowLabel(),
          },
        ])
      } finally {
        setSending(false)
      }
      return
    }

    let job
    try {
      job = await createBackgroundChatJob(trimmed, {
        mode: 'chat',
        topK: 15,
        finalK: 5,
        documentId: selectedDocId || null,
      })
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: `Désolé, la réponse n’a pas pu être démarrée : ${
            error instanceof Error ? error.message : 'service indisponible'
          }`,
          timestamp: nowLabel(),
        },
      ])
      setSending(false)
      return
    }
    started = true
    setStreamingId(assistantId)
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: 'assistant',
        content: '',
        sources,
        timestamp: nowLabel(),
        backgroundJobId: job.jobId,
        backgroundJobMode: 'chat',
        backgroundJobStatus: 'processing',
      },
    ])

    await streamBackgroundChatJob(
      job.jobId,
      {
        onSources: (incoming) => {
          sources = toMessageSources(incoming)
        },
        onDelta: (text) => {
          if (!started) {
            started = true
            setStreamingId(assistantId)
            setMessages((prev) => [
              ...prev,
              {
                id: assistantId,
                role: 'assistant',
                content: text,
                sources,
                timestamp: nowLabel(),
              },
            ])
          } else {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + text } : m,
              ),
            )
          }
        },
        onDone: ({ answer, metadata }) => {
          const elapsed =
            typeof metadata.generation_time === 'number'
              ? metadata.generation_time
              : measuredElapsed()
          // Fallback: if nothing streamed but the server returned a final
          // answer, render it so the user never sees an empty reply.
          if (!started && answer) {
            started = true
            setMessages((prev) => [
              ...prev,
              {
                id: assistantId,
                role: 'assistant',
                content: answer,
                sources,
                timestamp: nowLabel(),
                elapsed,
              },
            ])
            return
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    sources,
                    elapsed,
                    backgroundJobStatus: 'completed',
                  }
                : m,
            ),
          )
        },
        onError: (msg) => {
          if (!started) {
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: `Désolé, une erreur est survenue : ${msg}`,
                timestamp: nowLabel(),
              },
            ])
          } else {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: `${m.content}\n\n[Interrompu : ${msg}]`,
                      backgroundJobStatus: 'failed',
                    }
                  : m,
              ),
            )
          }
        },
      },
    )

    setStreamingId(null)
    setSending(false)
  }

  // Slash-command (agent picker) menu: shown while the composer holds only a
  // partial "/command" token (no space yet), filtered by what's typed.
  const slashToken = (() => {
    const trimmedStart = draft.replace(/^\s+/, '')
    if (!trimmedStart.startsWith('/')) return null
    const m = /^\/([\p{L}]*)$/u.exec(trimmedStart)
    return m ? m[1].toLowerCase() : null
  })()
  const slashMatches =
    slashToken === null
      ? []
      : SLASH_COMMANDS.filter((c) => c.key.startsWith(slashToken))
  const slashMenuOpen =
    chatMode === 'conversation' &&
    !slashClosed &&
    !sending &&
    slashMatches.length > 0
  const activeSlash = Math.min(slashIndex, Math.max(0, slashMatches.length - 1))

  const applySlash = (cmd: SlashCommand) => {
    setDraft(`${cmd.command} `)
    setSlashClosed(true)
    setSlashIndex(0)
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card
        className="flex h-[calc(100dvh-7.5rem)] min-h-[420px] flex-col overflow-hidden lg:col-span-2"
        padding="none"
      >
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-border bg-gradient-to-r from-brand to-brand-dark px-5 py-4 text-white">
          <div className="flex size-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
            <Logo className="size-6" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Assistant LegalLink</h2>
            <p className="flex items-center gap-1.5 text-xs text-blue-100">
              <span className="size-1.5 rounded-full bg-emerald-300 animate-pulse" />
              <span className="truncate">Portée : {scopeLabel}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={startNewConversation}
            disabled={sending}
            title="Démarrer une nouvelle conversation"
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-3 py-1.5 text-xs font-medium text-white backdrop-blur transition hover:bg-white/25 disabled:opacity-50"
          >
            <Plus className="size-3.5" />
            <span className="hidden sm:inline">Nouvelle</span>
          </button>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 space-y-4 overflow-y-auto bg-canvas/60 p-5 scrollbar-thin"
        >
          <div className="flex justify-center">
            <span className="rounded-full bg-white px-3 py-1 text-[11px] font-medium text-slate-500 shadow-sm ring-1 ring-border">
              {todayHeader()}
            </span>
          </div>

          {messages.map((message) => (
            <MessageRow
              key={message.id}
              message={message}
              streaming={message.id === streamingId}
              liveSeconds={
                message.id === streamingId ? elapsedMs / 1000 : undefined
              }
            />
          ))}

          {sending && !streamingId ? (
            <ThinkingBubble step={thinkingStep} seconds={elapsedMs / 1000} />
          ) : null}
        </div>

        {/* Composer */}
        <div className="border-t border-border bg-white p-4">
          <div className="mb-2 flex w-full rounded-xl border border-border bg-slate-50 p-1">
            <button
              type="button"
              disabled={sending}
              onClick={() => {
                setChatMode('conversation')
                setSlashClosed(false)
              }}
              className={cn(
                'flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50',
                chatMode === 'conversation'
                  ? 'bg-white text-brand shadow-sm ring-1 ring-border'
                  : 'text-slate-500 hover:text-slate-700',
              )}
            >
              <MessageSquare className="size-3.5" />
              Conversation
            </button>
            <button
              type="button"
              disabled={sending}
              onClick={() => {
                setChatMode('generation')
                setSlashClosed(true)
              }}
              className={cn(
                'flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50',
                chatMode === 'generation'
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-700',
              )}
            >
              <FileOutput className="size-3.5" />
              Génération PDF
            </button>
          </div>
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="flex shrink-0 items-center gap-1.5 font-medium text-slate-500">
              <Library className="size-3.5 text-brand" />
              Interroger
            </span>
            <select
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              disabled={sending}
              className="min-w-0 flex-1 truncate rounded-lg border border-border bg-slate-50 px-2.5 py-1.5 text-slate-700 outline-none transition focus:border-brand focus:bg-white focus:ring-2 focus:ring-brand/15 disabled:opacity-60"
            >
              <option value="">
                Tous les documents ({searchableDocs.length})
              </option>
              {searchableDocs.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          </div>
          {upload.isPending || activeUpload ? (
            <div className="mb-2 flex items-center gap-2 rounded-lg border border-border bg-slate-50 px-2.5 py-1.5 text-xs">
              {!upload.isPending && uploadReady ? (
                <FileText className="size-3.5 shrink-0 text-success" />
              ) : (
                <Loader2 className="size-3.5 shrink-0 animate-spin text-brand" />
              )}
              <span className="min-w-0 flex-1 truncate text-slate-600">
                {upload.isPending
                  ? 'Envoi du fichier…'
                  : `${activeUpload?.filename} · ${uploadReady ? 'prêt à être interrogé' : 'préparation en cours…'}`}
              </span>
              {activeUpload && !upload.isPending ? (
                <button
                  type="button"
                  onClick={() => setActiveUpload(null)}
                  className="shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-slate-400 transition hover:text-slate-600"
                >
                  Fermer
                </button>
              ) : null}
            </div>
          ) : null}
          {attachError ? (
            <p className="mb-2 text-xs text-danger">{attachError}</p>
          ) : null}
          <div className="relative">
            {slashMenuOpen ? (
              <div className="absolute bottom-full left-0 z-20 mb-2 w-full max-w-md overflow-hidden rounded-xl border border-border bg-white shadow-lg">
                <p className="border-b border-border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  Interroger un agent
                </p>
                {slashMatches.map((cmd, i) => {
                  const Icon = cmd.icon
                  return (
                    <button
                      key={cmd.key}
                      type="button"
                      // onMouseDown (not onClick) so the textarea keeps focus.
                      onMouseDown={(e) => {
                        e.preventDefault()
                        applySlash(cmd)
                      }}
                      onMouseEnter={() => setSlashIndex(i)}
                      className={cn(
                        'flex w-full items-center gap-2.5 px-3 py-2 text-left transition',
                        i === activeSlash ? 'bg-brand-soft' : 'hover:bg-slate-50',
                      )}
                    >
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                        <Icon className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1.5">
                          <span className="text-sm font-medium text-slate-800">
                            {cmd.label}
                          </span>
                          <code className="rounded bg-slate-100 px-1 text-[10px] text-slate-500">
                            {cmd.command}
                          </code>
                        </span>
                        <span className="block truncate text-[11px] text-slate-400">
                          {cmd.desc}
                        </span>
                      </span>
                    </button>
                  )
                })}
              </div>
            ) : null}
            <div className="flex items-end gap-2 rounded-2xl border border-border bg-slate-50 p-2 shadow-sm transition-all focus-within:border-brand focus-within:bg-white focus-within:ring-2 focus-within:ring-brand/15">
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => {
                  attachFile(e.target.files?.[0])
                  // Allow re-selecting the same file later.
                  e.target.value = ''
                }}
              />
              <button
                type="button"
                onClick={handleAttachClick}
                disabled={sending || upload.isPending}
                className="rounded-xl p-2.5 text-muted transition hover:bg-white hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Joindre un fichier PDF"
                title="Joindre un PDF"
              >
                {upload.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Paperclip className="size-4" />
                )}
              </button>
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value)
                  setSlashClosed(false)
                  setSlashIndex(0)
                }}
                onKeyDown={(e) => {
                  if (slashMenuOpen) {
                    if (e.key === 'ArrowDown') {
                      e.preventDefault()
                      setSlashIndex((i) => (i + 1) % slashMatches.length)
                      return
                    }
                    if (e.key === 'ArrowUp') {
                      e.preventDefault()
                      setSlashIndex(
                        (i) =>
                          (i - 1 + slashMatches.length) % slashMatches.length,
                      )
                      return
                    }
                    if (e.key === 'Enter' || e.key === 'Tab') {
                      e.preventDefault()
                      applySlash(slashMatches[activeSlash])
                      return
                    }
                    if (e.key === 'Escape') {
                      e.preventDefault()
                      setSlashClosed(true)
                      return
                    }
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send(draft)
                  }
                }}
                rows={1}
                placeholder={
                  chatMode === 'generation'
                    ? 'Décrivez le rapport PDF à générer…'
                    : 'Écrivez votre message… (tapez / pour choisir un agent)'
                }
                disabled={sending}
                className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm outline-none placeholder:text-slate-400 disabled:opacity-60"
              />
              <Button
                size="sm"
                className="rounded-xl"
                onClick={() => send(draft)}
                disabled={sending || !draft.trim()}
                leftIcon={
                  sending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Send className="size-4" />
                  )
                }
              >
                {sending ? 'Analyse…' : 'Envoyer'}
              </Button>
            </div>
          </div>
          <p className="mt-2 px-1 text-[11px] text-slate-400">
            {chatMode === 'generation' ? (
              <>
                Chaque demande crée et enregistre automatiquement un PDF ·
                Entrée pour envoyer
              </>
            ) : (
              <>
                Entrée pour envoyer · Maj + Entrée pour un retour à la ligne ·
                Tapez <code className="rounded bg-slate-100 px-1">/</code> pour
                interroger un agent
              </>
            )}
          </p>
        </div>
      </Card>

      <div className="space-y-4">
        <Card padding="lg">
          <CardHeader
            title="Conversations"
            subtitle={
              conversations.length
                ? `${conversations.length} enregistrée${conversations.length > 1 ? 's' : ''}`
                : 'Votre historique'
            }
            action={
              <button
                type="button"
                onClick={startNewConversation}
                disabled={sending}
                title="Nouvelle conversation"
                className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-brand/40 hover:text-brand disabled:opacity-50"
              >
                <Plus className="size-3.5" />
                Nouvelle
              </button>
            }
          />
          {conversations.length ? (
            <div className="mt-1 max-h-64 space-y-1 overflow-y-auto scrollbar-thin">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={cn(
                    'group flex items-center gap-2 rounded-lg border px-2.5 py-2 transition',
                    conv.id === activeId
                      ? 'border-brand/40 bg-brand-soft'
                      : 'border-transparent hover:border-border hover:bg-slate-50',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => openConversation(conv.id)}
                    disabled={sending}
                    className="flex min-w-0 flex-1 items-start gap-2 text-left disabled:cursor-not-allowed"
                  >
                    <MessageSquare
                      className={cn(
                        'mt-0.5 size-3.5 shrink-0',
                        conv.id === activeId ? 'text-brand' : 'text-slate-400',
                      )}
                    />
                    <span className="min-w-0">
                      <span
                        className={cn(
                          'block truncate text-xs font-medium',
                          conv.id === activeId
                            ? 'text-brand'
                            : 'text-slate-700',
                        )}
                      >
                        {conv.title}
                      </span>
                      <span className="block text-[10px] text-slate-400">
                        {relativeTime(conv.updatedAt)}
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteConversation(conv.id)}
                    title="Supprimer la conversation"
                    aria-label="Supprimer la conversation"
                    className="shrink-0 rounded-md p-1 text-slate-300 opacity-0 transition hover:bg-danger-soft hover:text-danger group-hover:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-slate-400">
              Vos conversations apparaîtront ici et seront conservées sur cet
              appareil.
            </p>
          )}
        </Card>

        <Card padding="lg">
          <CardHeader title="Document" subtitle="PDF uniquement · max 25 Mo" />
          <UploadZone onFiles={(files) => attachFile(files[0])} />
          {upload.isPending ? (
            <p className="mt-3 text-xs text-brand">Envoi du document…</p>
          ) : null}
          {activeUpload ? (
            <IngestionProgress
              documentId={activeUpload.documentId}
              filename={activeUpload.filename}
            />
          ) : null}
        </Card>

        <Card padding="lg">
          <CardHeader
            title="Suggestions"
            subtitle="Actions rapides"
            action={<Sparkles className="size-4 text-brand" />}
          />
          <div className="flex flex-col gap-2">
            {suggestions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => send(item.label)}
                disabled={sending}
                className="rounded-lg border border-border bg-white px-3 py-2.5 text-left text-sm text-slate-700 transition hover:border-brand/40 hover:bg-brand-soft hover:text-brand disabled:cursor-not-allowed disabled:opacity-60"
              >
                {item.label}
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
