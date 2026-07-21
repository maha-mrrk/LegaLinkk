import type { ChatAnswer } from '@/types'
import { api } from './api'

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
