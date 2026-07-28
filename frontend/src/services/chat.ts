import type { ChatAnswer, ChatDocumentResult, ChatSourceRef } from '@/types'
import { api, getToken } from './api'

export async function askQuestion(
  question: string,
  opts: { topK?: number; finalK?: number } = {},
): Promise<ChatAnswer> {
  const { data } = await api.post<ChatAnswer>('/chat/query', {
    question,
    top_k: opts.topK ?? 15,
    final_k: opts.finalK ?? 5,
  })
  return data
}

/**
 * Ask the assistant to produce a full, grounded HTML document (printable to
 * PDF / downloadable as a web page) instead of a plain-text chat answer.
 */
export async function generateDocument(
  question: string,
  opts: {
    topK?: number
    finalK?: number
    documentId?: string | null
    signal?: AbortSignal
  } = {},
): Promise<ChatDocumentResult> {
  const { data } = await api.post<ChatDocumentResult>(
    '/chat/document',
    {
      question,
      top_k: opts.topK ?? 15,
      final_k: opts.finalK ?? 5,
      ...(opts.documentId ? { document_id: opts.documentId } : {}),
    },
    { signal: opts.signal },
  )
  return data
}

/**
 * Render an already-generated HTML document to a real PDF (server-side
 * WeasyPrint) and return the binary blob for download.
 */
export async function downloadDocumentPdf(
  html: string,
  opts: {
    filename?: string
    title?: string
    sourceDocumentId?: string | null
    kind?: 'chat_report' | 'analysis_export'
    question?: string
  } = {},
): Promise<Blob> {
  const { data } = await api.post(
    '/chat/document/pdf',
    {
      html,
      filename: opts.filename,
      title: opts.title,
      source_document_id: opts.sourceDocumentId ?? undefined,
      kind: opts.kind ?? 'chat_report',
      question: opts.question,
    },
    { responseType: 'blob' },
  )
  return data as Blob
}

/**
 * Heuristic: does the user's message ask for a generated document / web page /
 * PDF rather than a normal chat answer? Kept intentionally focused to avoid
 * misfiring on ordinary questions that merely mention "document".
 */
export function wantsDocument(text: string): boolean {
  const t = text.toLowerCase()
  // A direct "génère" instruction always requests a generated PDF, even when
  // the user does not explicitly add "document", "téléchargeable" or "PDF".
  const directGeneration =
    /\b(?:génère|genere|générer|generer|générez|generez|générons|generons)\b/
  // A generation/analysis verb close to a document noun, or an explicit format
  // keyword. The verb list also covers analytical requests ("analyse",
  // "attribue un score", "synthétise", "dresse", "évalue", "donne un rapport"),
  // which are the natural way users ask for a full written report.
  const verb =
    /(génér|gener|génèr|genere|rédig|redig|cré[eé]|cree|prépar|prepar|établ|etabl|produi|fais|fabriqu|rédige|dress|analys|synth[eé]tis|synth[eè]tis|attribu|évalu|evalu|résum|resum|donne|liste)/
  const noun =
    /(pdf|page web|page html|site web|document|rapport|brochure|note de synth[eè]se|synth[eè]se|lettre|courrier|mémo|memo|compte[- ]rendu|fiche|note)/
  const explicit = /(en pdf|au format pdf|format pdf|en page web|en html|format html|télécharger|telecharger|imprimable)/
  return (
    directGeneration.test(t) ||
    explicit.test(t) ||
    (verb.test(t) && noun.test(t))
  )
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export interface StreamDonePayload {
  /** Full answer text — use as a fallback if no fragments were accumulated. */
  answer?: string
  metadata: Record<string, unknown>
}

export interface StreamHandlers {
  onSources?: (sources: ChatSourceRef[]) => void
  onDelta?: (text: string) => void
  onDone?: (payload: StreamDonePayload) => void
  onError?: (message: string) => void
}

export interface BackgroundChatJob {
  jobId: string
  status: 'queued'
}

export interface BackgroundJobHandlers extends StreamHandlers {
  onAgent?: (payload: {
    mode: 'single' | 'multi'
    domain?: string
    label?: string
  }) => void
  onStatus?: (message: string) => void
  onAnalyses?: (
    analyses: Array<{
      domain: string
      label: string
      status: string
      answer?: string
      sources?: ChatSourceRef[]
      message?: string
    }>,
  ) => void
}

export async function createBackgroundChatJob(
  question: string,
  opts: {
    mode: 'chat' | 'agent'
    topK?: number
    finalK?: number
    documentId?: string | null
  },
): Promise<BackgroundChatJob> {
  const { data } = await api.post<{ job_id: string; status: 'queued' }>(
    '/chat/jobs',
    {
      question,
      mode: opts.mode,
      top_k: opts.topK ?? 15,
      final_k: opts.finalK ?? 5,
      ...(opts.documentId ? { document_id: opts.documentId } : {}),
    },
  )
  return { jobId: data.job_id, status: data.status }
}

/** Replay all stored fragments and keep following the Redis-backed job. */
export async function streamBackgroundChatJob(
  jobId: string,
  handlers: BackgroundJobHandlers,
  opts: { signal?: AbortSignal } = {},
): Promise<void> {
  const token = getToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}/chat/jobs/${jobId}/stream`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: opts.signal,
    })
  } catch (err) {
    handlers.onError?.(err instanceof Error ? err.message : 'Erreur réseau')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.(`Le serveur a renvoyé une erreur (${response.status}).`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const handleEvent = (raw: string) => {
    const line = raw.trim()
    if (!line.startsWith('data:')) return
    try {
      const evt = JSON.parse(line.slice(5).trim()) as {
        type: string
        mode?: 'single' | 'multi'
        domain?: string
        label?: string
        message?: string
        sources?: ChatSourceRef[]
        analyses?: Parameters<NonNullable<BackgroundJobHandlers['onAnalyses']>>[0]
        text?: string
        answer?: string
        metadata?: Record<string, unknown>
      }
      if (evt.type === 'agent')
        handlers.onAgent?.({
          mode: evt.mode ?? 'single',
          domain: evt.domain,
          label: evt.label,
        })
      else if (evt.type === 'status') handlers.onStatus?.(evt.message ?? '')
      else if (evt.type === 'sources') handlers.onSources?.(evt.sources ?? [])
      else if (evt.type === 'analyses') handlers.onAnalyses?.(evt.analyses ?? [])
      else if (evt.type === 'delta') handlers.onDelta?.(evt.text ?? '')
      else if (evt.type === 'done')
        handlers.onDone?.({ answer: evt.answer, metadata: evt.metadata ?? {} })
      else if (evt.type === 'error')
        handlers.onError?.(evt.message ?? 'Une erreur est survenue.')
    } catch {
      /* Ignore malformed/heartbeat fragments. */
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) handleEvent(chunk)
  }
  if (buffer.trim()) handleEvent(buffer)
}

/**
 * Ask a question and receive the answer progressively (fragmented) over SSE.
 * The answer is rendered token-by-token instead of waiting for the full reply.
 */
export async function streamQuestion(
  question: string,
  handlers: StreamHandlers,
  opts: {
    topK?: number
    finalK?: number
    documentId?: string | null
    signal?: AbortSignal
  } = {},
): Promise<void> {
  const token = getToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        top_k: opts.topK ?? 15,
        final_k: opts.finalK ?? 5,
        ...(opts.documentId ? { document_id: opts.documentId } : {}),
      }),
      signal: opts.signal,
    })
  } catch (err) {
    handlers.onError?.(
      err instanceof Error ? err.message : 'Erreur réseau',
    )
    return
  }

  if (!response.ok || !response.body) {
    handlers.onError?.(`Le serveur a renvoyé une erreur (${response.status}).`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const handleEvent = (raw: string) => {
    const line = raw.trim()
    if (!line.startsWith('data:')) return
    const payload = line.slice(5).trim()
    if (!payload) return
    try {
      const evt = JSON.parse(payload) as {
        type: string
        sources?: ChatSourceRef[]
        text?: string
        answer?: string
        metadata?: Record<string, unknown>
        message?: string
      }
      if (evt.type === 'sources') handlers.onSources?.(evt.sources ?? [])
      else if (evt.type === 'delta') handlers.onDelta?.(evt.text ?? '')
      else if (evt.type === 'done')
        handlers.onDone?.({ answer: evt.answer, metadata: evt.metadata ?? {} })
      else if (evt.type === 'error')
        handlers.onError?.(evt.message ?? 'Une erreur est survenue.')
    } catch {
      /* ignore malformed fragments */
    }
  }

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) handleEvent(chunk)
  }
  if (buffer.trim()) handleEvent(buffer)
}
