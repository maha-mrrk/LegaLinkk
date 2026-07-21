import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyzeContract } from '@/services/analysis'
import { fetchDocuments, fetchRecentActivity, uploadDocument } from '@/services/documents'

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
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}
