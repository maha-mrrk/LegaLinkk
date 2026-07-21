import { useState } from 'react'
import { Loader2, Paperclip, Send, Sparkles } from 'lucide-react'
import { UploadZone } from '@/components/UploadZone'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { suggestions } from '@/data/mock'
import { useUploadDocument } from '@/hooks/useDocuments'
import { askQuestion } from '@/services/chat'
import { cn } from '@/lib/cn'
import type { ChatMessage } from '@/types'

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    'Bonjour. Déposez un contrat ou posez une question juridique — je peux résumer, détecter les risques et citer les références applicables.',
  timestamp: '',
}

function nowLabel(): string {
  return new Date().toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ConsultationPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const upload = useUploadDocument()

  const send = async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || sending) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: nowLabel(),
    }
    setMessages((prev) => [...prev, userMsg])
    setDraft('')
    setSending(true)

    try {
      const result = await askQuestion(trimmed)
      const cited = (result.sources ?? [])
        .map((s) => s.filename)
        .filter((v, i, arr): v is string => Boolean(v) && arr.indexOf(v) === i)
      const suffix = cited.length
        ? `\n\nSources : ${cited.join(', ')}`
        : ''
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: (result.answer || 'Aucune réponse disponible.') + suffix,
          timestamp: nowLabel(),
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            err instanceof Error
              ? `Désolé, une erreur est survenue : ${err.message}`
              : 'Désolé, une erreur est survenue.',
          timestamp: nowLabel(),
        },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="flex min-h-[70vh] flex-col lg:col-span-2" padding="none">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">
            Assistant LegalLink
          </h2>
          <p className="text-xs text-muted">
            Posez une question ou déposez un contrat pour démarrer
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5 scrollbar-thin">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex',
                message.role === 'user' ? 'justify-end' : 'justify-start',
              )}
            >
              <div
                className={cn(
                  'max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm transition-all',
                  message.role === 'user'
                    ? 'rounded-br-md bg-brand text-white'
                    : 'rounded-bl-md bg-slate-100 text-slate-800',
                )}
              >
                <p className="leading-relaxed whitespace-pre-wrap">
                  {message.content}
                </p>
                <p
                  className={cn(
                    'mt-1.5 text-[10px]',
                    message.role === 'user' ? 'text-blue-100' : 'text-slate-400',
                  )}
                >
                  {message.timestamp}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-border p-4">
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-slate-50 p-2 shadow-sm focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/15 transition-all">
            <button
              type="button"
              className="rounded-xl p-2.5 text-muted hover:bg-white hover:text-slate-700"
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
              className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm outline-none placeholder:text-slate-400"
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
      </Card>

      <div className="space-y-4">
        <Card padding="lg">
          <CardHeader
            title="Document"
            subtitle="PDF uniquement · max 25 Mo"
          />
          <UploadZone
            onFiles={(files) => {
              const file = files[0]
              if (file) upload.mutate(file)
            }}
          />
          {upload.isPending ? (
            <p className="mt-3 text-xs text-brand">Envoi en cours…</p>
          ) : null}
          {upload.isSuccess ? (
            <p className="mt-3 text-xs text-success">
              Fichier reçu : {upload.data.filename}
            </p>
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
                className="rounded-lg border border-border bg-white px-3 py-2.5 text-left text-sm text-slate-700 transition hover:border-brand/40 hover:bg-brand-soft hover:text-brand"
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
