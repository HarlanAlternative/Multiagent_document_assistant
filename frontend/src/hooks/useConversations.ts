import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteConversation, getConversation, listConversations } from "../api/conversations";

export function useConversations(projectId: string | null, conversationId: string | null) {
  const queryClient = useQueryClient();
  const listQuery = useQuery({
    queryKey: ["conversations", projectId],
    queryFn: () => listConversations(projectId!),
    enabled: Boolean(projectId),
  });

  const detailQuery = useQuery({
    queryKey: ["conversations", projectId, conversationId],
    queryFn: () => getConversation(conversationId!),
    enabled: Boolean(projectId && conversationId),
    staleTime: 10_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (targetConversationId: string) => deleteConversation(projectId!, targetConversationId),
    onSuccess: async (_, deletedConversationId) => {
      await queryClient.invalidateQueries({ queryKey: ["conversations", projectId] });
      queryClient.removeQueries({ queryKey: ["conversations", projectId, deletedConversationId] });
    },
  });

  return {
    listQuery,
    detailQuery,
    deleteMutation,
  };
}
