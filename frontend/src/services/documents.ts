import type {
  ActivityItem,
  DocumentItem,
  DocumentStatus,
  IngestionProgress,
  UploadResult,
} from '@/types'
import { api } from './api'

/** Raw document shape returned by the backend API. */
interface BackendDocument {
  id: string
  original_filename: string
  file_size: number
  upload_date: string
  status: 'uploaded' | 'processing' | 'processed' | 'failed'
  page_count: number | null
  extraction_method: string | null
  index_status: string
  indexed_at: string | null
  indexed_chunk_count: number | null
}

const STATUS_MAP: Record<BackendDocument['status'], DocumentStatus> = {
  processed: 'completed',
  processing: 'processing',
  failed: 'failed',
  uploaded: 'pending',
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const min = Math.round(diffMs / 60000)
  if (min < 1) return "À l'instant"
  if (min < 60) return `Il y a ${min} min`
  const hours = Math.round(min / 60)
  if (hours < 24) return `Il y a ${hours} h`
  const days = Math.round(hours / 24)
  return days === 1 ? 'Hier' : `Il y a ${days} j`
}

/** Map a backend document to the shape the UI expects. */
function toDocumentItem(doc: BackendDocument): DocumentItem {
  const isIndexed = doc.index_status === 'indexed'
  return {
    id: doc.id,
    filename: doc.original_filename,
    type: 'Contrat',
    date: formatDate(doc.upload_date),
    agents: isIndexed ? ['JU', 'RI', 'CO'] : [],
    score: 0,
    status: STATUS_MAP[doc.status] ?? 'pending',
    pageCount: doc.page_count ?? undefined,
    indexed: isIndexed,
  }
}

function subtitleFor(doc: BackendDocument): string {
  if (doc.status === 'failed') return 'Le traitement a échoué'
  if (doc.status === 'processing') return 'Analyse en cours'
  if (doc.status === 'uploaded') return "En file d'attente"
  if (doc.index_status === 'indexed') return 'Prêt à être analysé'
  return 'Traitement terminé'
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const { data } = await api.get<{ items: BackendDocument[] }>('/documents')
  return data.items.map(toDocumentItem)
}

interface BackendUploadResponse {
  document_id: string
  task_id: string | null
  status: string
  filename: string
  message: string
}

/**
 * Upload a contract. The backend queues processing in the background and
 * returns immediately with a task id — poll {@link fetchDocumentProgress} for
 * live status.
 */
export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<BackendUploadResponse>('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return {
    documentId: data.document_id,
    taskId: data.task_id,
    status: data.status,
    filename: data.filename,
    message: data.message,
  }
}

/** Fetch the live processing progress for a document. */
export async function fetchDocumentProgress(
  documentId: string,
): Promise<IngestionProgress> {
  const { data } = await api.get<IngestionProgress>(
    `/documents/${documentId}/progress`,
  )
  return data
}

/** No dedicated /activity endpoint — derive it from the most recent documents. */
export async function fetchRecentActivity(): Promise<ActivityItem[]> {
  const { data } = await api.get<{ items: BackendDocument[] }>('/documents')
  return data.items.slice(0, 6).map((doc) => ({
    id: doc.id,
    title: doc.original_filename,
    subtitle: subtitleFor(doc),
    timeAgo: timeAgo(doc.upload_date),
    status: STATUS_MAP[doc.status] ?? 'pending',
  }))
}
