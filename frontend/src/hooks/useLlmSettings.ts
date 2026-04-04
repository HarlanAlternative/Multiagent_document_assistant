import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getLlmSettings, getSearchSettings, listProviderModels, updateLlmSettings, updateSearchSettings } from "../api/settings";
import type { LlmSettingsUpdateRequest, ModelCatalogRequest, SearchSettingsUpdateRequest } from "../types/api";

export function useLlmSettings() {
  const queryClient = useQueryClient();

  const llmSettingsQuery = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: getLlmSettings,
  });

  const searchSettingsQuery = useQuery({
    queryKey: ["settings", "search"],
    queryFn: getSearchSettings,
  });

  const updateLlmSettingsMutation = useMutation({
    mutationFn: (payload: LlmSettingsUpdateRequest) => updateLlmSettings(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "llm"] });
      await queryClient.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const loadModelsMutation = useMutation({
    mutationFn: (payload: ModelCatalogRequest) => listProviderModels(payload),
  });

  const updateSearchSettingsMutation = useMutation({
    mutationFn: (payload: SearchSettingsUpdateRequest) => updateSearchSettings(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "search"] });
      await queryClient.invalidateQueries({ queryKey: ["health"] });
    },
  });

  return {
    llmSettingsQuery,
    searchSettingsQuery,
    updateLlmSettingsMutation,
    loadModelsMutation,
    updateSearchSettingsMutation,
  };
}
