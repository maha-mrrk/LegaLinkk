import { documents as mockDocuments, analysisResult, recentActivity } from '@/data/mock'
import type { AnalysisResult, DocumentItem } from '@/types'
import { api } from './api'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export async function fetchDocuments(): Promise<DocumentItem[]> {
  if (USE_MOCK) {
    await delay(350)
    return mockDocuments
  }
  const { data } = await api.get<{ items: DocumentItem[] }>('/documents')
  return data.items
}

export async function fetchDocument(id: string): Promise<DocumentItem | undefined> {
  if (USE_MOCK) {
    await delay(200)
    return mockDocuments.find((d) => d.id === id)
  }
  const { data } = await api.get<DocumentItem>(`/documents/${id}`)
  return data
}

export async function fetchAnalysis(id: string): Promise<AnalysisResult> {
  if (USE_MOCK) {
    await delay(400)
    return { ...analysisResult, id }
  }
  const { data } = await api.get<AnalysisResult>(`/analyses/${id}`)
  return data
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  if (USE_MOCK) {
    await delay(800)
    return {
      id: crypto.randomUUID(),
      filename: file.name,
      type: 'Commercial',
      date: new Date().toLocaleString('fr-FR'),
      agents: ['LA'],
      score: 0,
      status: 'processing',
      pageCount: undefined,
    }
  }
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<DocumentItem>('/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function fetchRecentActivity(): Promise<typeof recentActivity> {
  if (USE_MOCK) {
    await delay(250)
    return recentActivity
  }
  const { data } = await api.get<typeof recentActivity>('/activity')
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
