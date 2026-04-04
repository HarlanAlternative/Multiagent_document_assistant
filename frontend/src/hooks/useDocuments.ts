import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, getDocument, listDocuments, reindexDocument, renameDocument, uploadDocument } from "../api/documents";

export function useDocuments(projectId: string | null) {
  const queryClient = useQueryClient();
  const documentsKey = ["documents", projectId];

  const documentsQuery = useQuery({
    queryKey: documentsKey,
    queryFn: () => listDocuments(projectId!),
    enabled: Boolean(projectId),
  });

  const detailQueries = useQueries({
    queries:
      documentsQuery.data?.items.map((document) => ({
        queryKey: ["documents", projectId, document.id],
        queryFn: () => getDocument(document.id, projectId!),
        staleTime: 15_000,
      })) ?? [],
  });

  const detailMap = new Map(
    (documentsQuery.data?.items ?? []).map((document, index) => [document.id, detailQueries[index]?.data]),
  );

  const invalidateDocuments = async () => {
    await queryClient.invalidateQueries({ queryKey: documentsKey });
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDocument(projectId!, file),
    onSuccess: invalidateDocuments,
  });

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(projectId!, documentId),
    onSuccess: async (_, documentId) => {
      await queryClient.invalidateQueries({ queryKey: documentsKey });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.removeQueries({ queryKey: ["documents", projectId, documentId] });
    },
  });

  const reindexMutation = useMutation({
    mutationFn: (documentId: string) => reindexDocument(projectId!, documentId),
    onSuccess: invalidateDocuments,
  });

  const renameMutation = useMutation({
    mutationFn: ({ documentId, filename }: { documentId: string; filename: string }) =>
      renameDocument(projectId!, documentId, { filename }),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: documentsKey });
      await queryClient.invalidateQueries({ queryKey: ["documents", projectId, variables.documentId] });
    },
  });

  return {
    documentsQuery,
    detailMap,
    uploadMutation,
    deleteMutation,
    reindexMutation,
    renameMutation,
  };
}
