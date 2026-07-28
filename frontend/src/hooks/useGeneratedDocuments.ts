import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteGeneratedDocument,
  fetchGeneratedDocuments,
} from '@/services/generatedDocuments'

export function useGeneratedDocuments(sourceDocumentId?: string | null) {
  return useQuery({
    queryKey: ['generated-documents', sourceDocumentId ?? 'all'],
    queryFn: () => fetchGeneratedDocuments(sourceDocumentId),
  })
}

export function useDeleteGeneratedDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteGeneratedDocument,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['generated-documents'] }),
  })
}
