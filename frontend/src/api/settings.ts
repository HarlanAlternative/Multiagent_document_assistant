import type {
  LlmSettings,
  LlmSettingsUpdateRequest,
  ModelCatalogRequest,
  ModelCatalogResponse,
  SearchSettings,
  SearchSettingsUpdateRequest,
} from "../types/api";
import { getJson, postJson, putJson } from "./client";

export function getLlmSettings(): Promise<LlmSettings> {
  return getJson<LlmSettings>("/settings/llm");
}

export function updateLlmSettings(payload: LlmSettingsUpdateRequest): Promise<LlmSettings> {
  return putJson<LlmSettings, LlmSettingsUpdateRequest>("/settings/llm", payload);
}

export function getSearchSettings(): Promise<SearchSettings> {
  return getJson<SearchSettings>("/settings/search");
}

export function updateSearchSettings(payload: SearchSettingsUpdateRequest): Promise<SearchSettings> {
  return putJson<SearchSettings, SearchSettingsUpdateRequest>("/settings/search", payload);
}

export function listProviderModels(payload: ModelCatalogRequest): Promise<ModelCatalogResponse> {
  return postJson<ModelCatalogResponse, ModelCatalogRequest>("/settings/llm/models", payload);
}
