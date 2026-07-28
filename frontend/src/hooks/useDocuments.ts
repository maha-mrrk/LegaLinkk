import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchAnalysisJob,
  startAnalysisJob,
} from '@/services/analysis'
import { useAuth } from '@/context/AuthContext'
import type { DocumentItem, LegalAnalysis } from '@/types'
import {
  deleteDocument,
  fetchDocumentProgress,
  fetchDocuments,
  fetchRecentActivity,
  uploadDocument,
} from '@/services/documents'

const LEGAL_ANALYSIS_CACHE_VERSION = 4
const ANALYSIS_JOB_PREFIX = 'legallink.analysis-job.v1'

function analysisJobKey(userId: string, documentId: string) {
  return `${ANALYSIS_JOB_PREFIX}.${userId}.${documentId}`
}

function isNotFound(error: unknown) {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    (error as { response?: { status?: number } }).response?.status === 404
  )
}

async function pause(ms: number, signal?: AbortSignal) {
  await new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

async function followAnalysisJob(jobId: string, signal?: AbortSignal) {
  while (true) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    const job = await fetchAnalysisJob(jobId)
    if (job.status === 'completed' && job.result) return job.result
    if (job.status === 'failed') {
      throw new Error(
        job.error ?? "L'analyse n'a pas pu être terminée. Veuillez réessayer.",
      )
    }
    await pause(1500, signal)
  }
}

async function runDurableAnalysis(params: {
  userId: string
  documentId: string
  forceRefresh?: boolean
  signal?: AbortSignal
}) {
  const key = analysisJobKey(params.userId, params.documentId)
  if (!params.forceRefresh) {
    const existingJobId = localStorage.getItem(key)
    if (existingJobId) {
      try {
        return await followAnalysisJob(existingJobId, params.signal)
      } catch (error) {
        if (!isNotFound(error)) throw error
        localStorage.removeItem(key)
      }
    }
  }

  const job = await startAnalysisJob({
    documentId: params.documentId,
    forceRefresh: params.forceRefresh,
  })
  localStorage.setItem(key, job.job_id)
  return followAnalysisJob(job.job_id, params.signal)
}

function legalAnalysisKey(documentId: string | undefined) {
  return ['legal-analysis', LEGAL_ANALYSIS_CACHE_VERSION, documentId] as const
}

function updateDocumentScore(
  queryClient: ReturnType<typeof useQueryClient>,
  documentId: string | undefined,
  analysis: LegalAnalysis,
) {
  if (!documentId) return
  queryClient.setQueryData<DocumentItem[]>(['documents'], (documents) =>
    documents?.map((document) =>
      document.id === documentId
        ? { ...document, score: analysis.risk_score }
        : document,
    ),
  )
}

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
  })
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ['activity'],
    queryFn: fetchRecentActivity,
  })
}

/**
 * Loads a contract analysis. The backend returns the persisted result when it
 * exists, otherwise it calculates and stores it.
 */
export function useLegalAnalysis(documentId: string | undefined) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useQuery({
    queryKey: legalAnalysisKey(documentId),
    queryFn: async ({ signal }) => {
      const analysis = await runDurableAnalysis({
        userId: user?.id ?? '',
        documentId: documentId as string,
        signal,
      })
      updateDocumentScore(queryClient, documentId, analysis)
      return analysis
    },
    enabled: Boolean(documentId && user?.id),
    staleTime: 30 * 60_000,
    retry: 0,
  })
}

/** Explicitly calculate a new version and replace the local cached result. */
export function useRefreshLegalAnalysis(documentId: string | undefined) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation({
    mutationFn: () =>
      runDurableAnalysis({
        userId: user?.id ?? '',
        documentId: documentId as string,
        forceRefresh: true,
      }),
    onSuccess: (analysis) => {
      queryClient.setQueryData(legalAnalysisKey(documentId), analysis)
      updateDocumentScore(queryClient, documentId, analysis)
    },
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      // A new document appears immediately (queued); the list refreshes again
      // once processing completes (see useDocumentProgress).
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}

/** Permanently delete a document, then refresh the library + recent activity. */
export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: (_data, documentId) => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['activity'] })
      queryClient.removeQueries({ queryKey: ['legal-analysis', documentId] })
    },
  })
}

/**
 * Poll live processing progress for a document. Polling stops automatically
 * once the pipeline reaches a terminal state (completed or failed).
 */
export function useDocumentProgress(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document-progress', documentId],
    queryFn: () => fetchDocumentProgress(documentId as string),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 1500
    },
    // Progress changes constantly; always consider it stale so polls re-render.
    staleTime: 0,
    gcTime: 0,
  })
}
