import type { GeneratedDocumentItem } from '@/types'
import { api } from './api'

interface BackendGeneratedDocument {
  id: string
  source_document_id: string | null
  source_document_filename: string | null
  title: string
  original_filename: string
  file_size: number
  kind: 'chat_report' | 'analysis_export'
  question: string | null
  created_at: string
}

function mapItem(item: BackendGeneratedDocument): GeneratedDocumentItem {
  return {
    id: item.id,
    sourceDocumentId: item.source_document_id,
    sourceDocumentFilename: item.source_document_filename,
    title: item.title,
    filename: item.original_filename,
    fileSize: item.file_size,
    kind: item.kind,
    question: item.question,
    createdAt: item.created_at,
  }
}

export async function fetchGeneratedDocuments(
  sourceDocumentId?: string | null,
): Promise<GeneratedDocumentItem[]> {
  const { data } = await api.get<{ items: BackendGeneratedDocument[] }>(
    '/generated-documents',
    {
      params: sourceDocumentId
        ? { source_document_id: sourceDocumentId }
        : undefined,
    },
  )
  return data.items.map(mapItem)
}

export async function fetchGeneratedDocumentBlob(id: string): Promise<Blob> {
  const { data } = await api.get(`/generated-documents/${id}/file`, {
    responseType: 'blob',
  })
  return data as Blob
}

export async function deleteGeneratedDocument(id: string): Promise<void> {
  await api.delete(`/generated-documents/${id}`)
}
