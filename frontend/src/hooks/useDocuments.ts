import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeContract } from '@/services/analysis'
import {
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

/** Runs the legal analysis for a given contract (backend legal assistant). */
export function useLegalAnalysis(documentId: string | undefined) {
  return useQuery({
    queryKey: ['legal-analysis', documentId],
    queryFn: () => analyzeContract({ documentId }),
    enabled: Boolean(documentId),
    staleTime: 5 * 60_000,
    retry: 0,
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
