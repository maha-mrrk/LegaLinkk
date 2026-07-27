import type { AgentQueryResult, ChatSourceRef } from '@/types'
import { api, getToken } from './api'

/**
 * Query the multi-agent LangGraph (`POST /agents/query`).
 *
 * The routing is driven entirely by the leading command in `question`:
 * - `/legal …` | `/finance …` | `/compliance …` → only that agent answers
 *   (`mode: "single"`).
 * - no leading command → the three agents run and a synthesis agent produces a
 *   final recommendation from their three analyses (`mode: "multi"`).
 */
export async function queryAgents(
  question: string,
  opts: {
    topK?: number
    finalK?: number
    documentId?: string | null
    signal?: AbortSignal
  } = {},
): Promise<AgentQueryResult> {
  const { data } = await api.post<AgentQueryResult>(
    '/agents/query',
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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

/** One agent analysis pushed by the streaming endpoint (multi mode). */
export interface StreamAgentAnalysis {
  domain: string
  label: string
  status: string
  answer: string
  sources?: ChatSourceRef[]
  message?: string
}

export interface StreamAgentsHandlers {
  /** Fired once before content: which agent (single) or that all run (multi). */
  onAgent?: (info: { mode: 'single' | 'multi'; domain?: string; label?: string }) => void
  /** Multi mode: progress ping while an individual agent is analysing. */
  onStatus?: (message: string) => void
  /** Single mode: the grounded sources for the streamed answer. */
  onSources?: (sources: ChatSourceRef[]) => void
  /** Multi mode: the three individual analyses behind the synthesis. */
  onAnalyses?: (analyses: StreamAgentAnalysis[]) => void
  /** Incremental answer / synthesis fragments. */
  onDelta?: (text: string) => void
  onDone?: (payload: { answer?: string; metadata: Record<string, unknown> }) => void
  onError?: (message: string) => void
}

/**
 * Stream an agent answer over SSE (`POST /agents/stream`), fragmented like the
 * normal chat stream.
 *
 * - `/legal|/finance|/compliance …` → streams ONE agent's grounded answer.
 * - no leading command → runs the three agents then streams the synthesis.
 */
export async function streamAgents(
  question: string,
  handlers: StreamAgentsHandlers,
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
    response = await fetch(`${API_BASE}/agents/stream`, {
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
    const payload = line.slice(5).trim()
    if (!payload) return
    try {
      const evt = JSON.parse(payload) as {
        type: string
        mode?: 'single' | 'multi'
        domain?: string
        label?: string
        message?: string
        sources?: ChatSourceRef[]
        analyses?: StreamAgentAnalysis[]
        text?: string
        answer?: string
        metadata?: Record<string, unknown>
      }
      switch (evt.type) {
        case 'agent':
          handlers.onAgent?.({
            mode: evt.mode ?? 'single',
            domain: evt.domain,
            label: evt.label,
          })
          break
        case 'status':
          handlers.onStatus?.(evt.message ?? '')
          break
        case 'sources':
          handlers.onSources?.(evt.sources ?? [])
          break
        case 'analyses':
          handlers.onAnalyses?.(evt.analyses ?? [])
          break
        case 'delta':
          handlers.onDelta?.(evt.text ?? '')
          break
        case 'done':
          handlers.onDone?.({ answer: evt.answer, metadata: evt.metadata ?? {} })
          break
        case 'error':
          handlers.onError?.(evt.message ?? 'Une erreur est survenue.')
          break
        default:
          break
      }
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
