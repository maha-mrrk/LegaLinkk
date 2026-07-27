import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeContract } from '@/services/analysis'
import {
  deleteDocument,
  fetchDocumentProgress,
  fetchDocuments,
  fetchRecentActivity,
  uploadDocument,
} from '@/services/documents'

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
  return useQuery({
    queryKey: ['legal-analysis', documentId],
    queryFn: () => analyzeContract({ documentId }),
    enabled: Boolean(documentId),
    staleTime: 30 * 60_000,
    retry: 0,
  })
}

/** Explicitly calculate a new version and replace the local cached result. */
export function useRefreshLegalAnalysis(documentId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      analyzeContract({ documentId, forceRefresh: true }),
    onSuccess: (analysis) => {
      queryClient.setQueryData(['legal-analysis', documentId], analysis)
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
