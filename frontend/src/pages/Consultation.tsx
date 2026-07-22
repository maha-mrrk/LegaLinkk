import { useEffect, useRef, useState } from 'react'
import {
  Download,
  FileText,
  Library,
  Loader2,
  Paperclip,
  Printer,
  Scale,
  Send,
  Sparkles,
  User,
} from 'lucide-react'
import { UploadZone } from '@/components/UploadZone'
import { IngestionProgress } from '@/components/IngestionProgress'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { suggestions } from '@/data/mock'
import { useDocuments, useUploadDocument } from '@/hooks/useDocuments'
import { generateDocument, streamQuestion, wantsDocument } from '@/services/chat'
import { cn } from '@/lib/cn'
import type { ChatMessage } from '@/types'

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

function DocumentCard({ html }: { html: string }) {
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
            onClick={() => printDocument(html)}
            className="inline-flex items-center gap-1 rounded-lg bg-brand px-2.5 py-1 text-[11px] font-medium text-white transition hover:bg-brand-dark"
          >
            <Printer className="size-3" /> Imprimer / PDF
          </button>
          <button
            type="button"
            onClick={() => downloadDocument(html)}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-brand/40 hover:text-brand"
          >
            <Download className="size-3" /> Télécharger
          </button>
        </div>
      </div>
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
      <Scale className="size-4" />
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
          <p className="leading-relaxed whitespace-pre-wrap">
            {message.content}
            {streaming ? (
              <span className="ml-0.5 inline-block h-3.5 w-[3px] translate-y-0.5 animate-pulse rounded-sm bg-brand align-middle" />
            ) : null}
          </p>
          {message.document ? <DocumentCard html={message.document} /> : null}
          {message.sources?.length ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-white/20 pt-2">
              {message.sources.map((src) => (
                <span
                  key={src}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
                    isUser
                      ? 'bg-white/15 text-blue-50'
                      : 'bg-brand-soft text-brand',
                  )}
                >
                  <FileText className="size-3" />
                  {src}
                </span>
              ))}
            </div>
          ) : null}
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
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Bonjour. Déposez un contrat ou posez une question juridique — je peux résumer, détecter les risques et citer les références applicables.',
      timestamp: nowLabel(),
    },
  ])
  const [draft, setDraft] = useState('')
  const [selectedDocId, setSelectedDocId] = useState('')
  const [sending, setSending] = useState(false)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [thinkingStep, setThinkingStep] = useState(0)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [activeUpload, setActiveUpload] = useState<{
    documentId: string
    filename: string
  } | null>(null)
  const upload = useUploadDocument()
  const { data: documents } = useDocuments()
  const scrollRef = useRef<HTMLDivElement>(null)
  const startRef = useRef<number>(0)

  // Only indexed documents can be searched; the empty value means "all".
  const searchableDocs = (documents ?? []).filter((d) => d.indexed)
  const selectedDoc = searchableDocs.find((d) => d.id === selectedDocId)
  const scopeLabel = selectedDoc
    ? selectedDoc.filename
    : 'Toute la bibliothèque'

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

  const send = async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || sending) return

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
    let sources: string[] = []

    const measuredElapsed = () =>
      Math.round(((performance.now() - startRef.current) / 1000) * 10) / 10

    // Document mode: the user asked for a full document / web page / PDF.
    if (wantsDocument(trimmed)) {
      try {
        const result = await generateDocument(trimmed, {
          topK: 15,
          finalK: 5,
          documentId: selectedDocId || null,
        })
        const docSources = result.sources
          .map((s) => s.filename)
          .filter((v, i, arr): v is string => Boolean(v) && arr.indexOf(v) === i)
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

    await streamQuestion(
      trimmed,
      {
        onSources: (incoming) => {
          sources = incoming
            .map((s) => s.filename)
            .filter(
              (v, i, arr): v is string => Boolean(v) && arr.indexOf(v) === i,
            )
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
              m.id === assistantId ? { ...m, sources, elapsed } : m,
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
                  ? { ...m, content: `${m.content}\n\n[Interrompu : ${msg}]` }
                  : m,
              ),
            )
          }
        },
      },
      { topK: 15, finalK: 5, documentId: selectedDocId || null },
    )

    setStreamingId(null)
    setSending(false)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card
        className="flex min-h-[72vh] flex-col overflow-hidden lg:col-span-2"
        padding="none"
      >
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-border bg-gradient-to-r from-brand to-brand-dark px-5 py-4 text-white">
          <div className="flex size-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
            <Scale className="size-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">Assistant LegalLink</h2>
            <p className="flex items-center gap-1.5 text-xs text-blue-100">
              <span className="size-1.5 rounded-full bg-emerald-300 animate-pulse" />
              <span className="truncate">Portée : {scopeLabel}</span>
            </p>
          </div>
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
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-slate-50 p-2 shadow-sm transition-all focus-within:border-brand focus-within:bg-white focus-within:ring-2 focus-within:ring-brand/15">
            <button
              type="button"
              className="rounded-xl p-2.5 text-muted transition hover:bg-white hover:text-slate-700"
              aria-label="Joindre un fichier"
            >
              <Paperclip className="size-4" />
            </button>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send(draft)
                }
              }}
              rows={1}
              placeholder="Écrivez votre message…"
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
          <p className="mt-2 px-1 text-[11px] text-slate-400">
            Entrée pour envoyer · Maj + Entrée pour un retour à la ligne
          </p>
        </div>
      </Card>

      <div className="space-y-4">
        <Card padding="lg">
          <CardHeader title="Document" subtitle="PDF uniquement · max 25 Mo" />
          <UploadZone
            onFiles={(files) => {
              const file = files[0]
              if (!file) return
              upload.mutate(file, {
                onSuccess: (result) => {
                  setActiveUpload({
                    documentId: result.documentId,
                    filename: result.filename,
                  })
                },
              })
            }}
          />
          {upload.isPending ? (
            <p className="mt-3 text-xs text-brand">Envoi du document…</p>
          ) : null}
          {upload.isError ? (
            <p className="mt-3 text-xs text-danger">
              {upload.error instanceof Error
                ? upload.error.message
                : "L'envoi a échoué. Veuillez réessayer."}
            </p>
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
