import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchAnalysis,
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

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ['analysis', id],
    queryFn: () => fetchAnalysis(id),
    enabled: Boolean(id),
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
