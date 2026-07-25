import { useCallback, useState } from 'react'
import type { ChatMessage } from '@/types'

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

const STORAGE_KEY = 'legallink.conversations.v1'
const MAX_CONVERSATIONS = 50

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== 'object') return false
  const c = value as Record<string, unknown>
  return typeof c.id === 'string' && Array.isArray(c.messages)
}

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return (parsed as unknown[])
      .filter(isConversation)
      .sort((a, b) => b.updatedAt - a.updatedAt)
  } catch {
    return []
  }
}

/** Drop generated HTML documents — they are large and blow the storage quota. */
function stripDocuments(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((m) =>
      m.document ? { ...m, document: undefined } : m,
    ),
  }
}

/**
 * Persist best-effort. localStorage is capped (~5 MB), so on QuotaExceededError
 * we progressively shed generated documents and then oldest conversations rather
 * than losing the whole history.
 */
function persist(list: Conversation[]): void {
  const attempts: Conversation[][] = [
    list,
    list.map(stripDocuments),
    list.slice(0, 15).map(stripDocuments),
    list.slice(0, 5).map(stripDocuments),
  ]
  for (const attempt of attempts) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(attempt))
      return
    } catch {
      // Try a smaller payload.
    }
  }
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(() =>
    load(),
  )

  const upsert = useCallback((conversation: Conversation) => {
    setConversations((prev) => {
      const next = [
        conversation,
        ...prev.filter((c) => c.id !== conversation.id),
      ]
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, MAX_CONVERSATIONS)
      persist(next)
      return next
    })
  }, [])

  const remove = useCallback((id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      persist(next)
      return next
    })
  }, [])

  return { conversations, upsert, remove }
}
