import { useMutation, useQueryClient } from "@tanstack/react-query";

import { askQuestion } from "../api/chat";

export function useChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: askQuestion,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
