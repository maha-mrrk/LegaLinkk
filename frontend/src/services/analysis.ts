import type { LegalAnalysis } from '@/types'
import { api } from './api'

const DEFAULT_QUESTION =
  'Analyse ce contrat : résume les provisions clés, identifie les obligations et ' +
  'les droits de chaque partie, détecte les clauses manquantes ou ambiguës et ' +
  'signale les risques juridiques.'

export async function analyzeContract(params: {
  question?: string
  documentId?: string
  topK?: number
  finalK?: number
}): Promise<LegalAnalysis> {
  const { data } = await api.post<LegalAnalysis>('/agents/legal/analyze', {
    question: params.question?.trim() || DEFAULT_QUESTION,
    document_id: params.documentId,
    top_k: params.topK ?? 15,
    final_k: params.finalK ?? 5,
  })
  return data
}
