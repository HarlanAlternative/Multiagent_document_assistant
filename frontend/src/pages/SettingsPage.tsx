import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { Button } from "../components/common/Button";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { useWorkspace } from "../components/layout/WorkspaceProvider";

type ProviderPreset = {
  id: string;
  label: string;
  description: string;
  baseUrl: string;
  wireApi: string;
  models: string[];
  defaultEmbeddingProvider?: string;
  defaultEmbeddingModel?: string;
  defaultVectorStore?: string;
  defaultRegion?: string;
  compatibilityNote?: string;
};

const providerPresets: ProviderPreset[] = [
  {
    id: "openai",
    label: "OpenAI",
    description: "Official OpenAI endpoint.",
    baseUrl: "https://api.openai.com/v1",
    wireApi: "responses",
    models: ["gpt-5-mini", "gpt-5", "gpt-5-nano", "gpt-4.1-mini"],
    defaultEmbeddingProvider: "openai",
    defaultEmbeddingModel: "text-embedding-3-large",
    defaultVectorStore: "qdrant",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    description: "One API for multiple providers through an OpenAI-compatible endpoint.",
    baseUrl: "https://openrouter.ai/api/v1",
    wireApi: "chat_completions",
    models: [
      "openai/gpt-5-mini",
      "google/gemini-2.5-pro",
      "anthropic/claude-sonnet-4",
      "deepseek/deepseek-chat-v3",
    ],
  },
  {
    id: "bedrock",
    label: "Amazon Bedrock (AWS)",
    description: "AWS-managed model inference service using native Bedrock chat and embedding APIs.",
    baseUrl: "",
    wireApi: "bedrock",
    models: ["anthropic.claude-3-5-sonnet-20240620-v1:0", "amazon.nova-pro-v1:0", "amazon.nova-lite-v1:0"],
    defaultEmbeddingProvider: "bedrock",
    defaultEmbeddingModel: "amazon.titan-embed-text-v2:0",
    defaultVectorStore: "qdrant",
    defaultRegion: "us-east-1",
    compatibilityNote: "This dropdown is for model backends only. Amazon Bedrock here means the AWS inference service, not a memory or orchestration framework.",
  },
  {
    id: "gemini",
    label: "Gemini",
    description: "Google Gemini model names for a compatible gateway or router.",
    baseUrl: "",
    wireApi: "chat_completions",
    models: ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
    compatibilityNote: "This app currently expects an OpenAI-compatible endpoint. Use a compatible gateway or router for Gemini.",
  },
  {
    id: "claude",
    label: "Claude",
    description: "Anthropic Claude model names for a compatible gateway or router.",
    baseUrl: "",
    wireApi: "chat_completions",
    models: ["claude-sonnet-4-0", "claude-opus-4-0", "claude-3-7-sonnet-latest"],
    compatibilityNote: "Native Anthropic API is not wired here yet. Use an OpenAI-compatible gateway or router for Claude.",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    description: "DeepSeek model names for its compatible endpoint or another router.",
    baseUrl: "https://api.deepseek.com/v1",
    wireApi: "chat_completions",
    models: ["deepseek-chat", "deepseek-reasoner"],
  },
  {
    id: "custom",
    label: "Custom",
    description: "Bring your own compatible endpoint, wire API, and model name.",
    baseUrl: "",
    wireApi: "responses",
    models: [],
  },
];

export function SettingsPage() {
  const { llmSettingsQuery, searchSettingsQuery, updateLlmSettingsMutation, updateSearchSettingsMutation, loadModelsMutation } = useWorkspace();
  const [apiKey, setApiKey] = useState("");
  const [providerName, setProviderName] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [wireApi, setWireApi] = useState("responses");
  const [awsRegion, setAwsRegion] = useState("us-east-1");
  const [awsAccessKeyId, setAwsAccessKeyId] = useState("");
  const [awsSecretAccessKey, setAwsSecretAccessKey] = useState("");
  const [awsSessionToken, setAwsSessionToken] = useState("");
  const [embeddingProvider, setEmbeddingProvider] = useState("deterministic");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [vectorStore, setVectorStore] = useState("qdrant");
  const [chatModel, setChatModel] = useState("gpt-5-mini");
  const [searchEnabled, setSearchEnabled] = useState(true);
  const [searchProvider, setSearchProvider] = useState("duckduckgo");
  const [searchApiKey, setSearchApiKey] = useState("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [searchSuccessMessage, setSearchSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!llmSettingsQuery.data) {
      return;
    }
    setProviderName(llmSettingsQuery.data.provider_name || "openai");
    setBaseUrl(llmSettingsQuery.data.base_url || "https://api.openai.com/v1");
    setWireApi(llmSettingsQuery.data.wire_api || "responses");
    setAwsRegion(llmSettingsQuery.data.aws_region || "us-east-1");
    setEmbeddingProvider(llmSettingsQuery.data.embedding_provider || "deterministic");
    setEmbeddingModel(llmSettingsQuery.data.embedding_model || "");
    setVectorStore(llmSettingsQuery.data.vector_store || "qdrant");
    setChatModel(llmSettingsQuery.data.chat_model || "gpt-5-mini");
    setAvailableModels([]);
  }, [llmSettingsQuery.data]);

  useEffect(() => {
    if (!searchSettingsQuery.data) {
      return;
    }
    setSearchEnabled(searchSettingsQuery.data.search_enabled);
    setSearchProvider(searchSettingsQuery.data.search_provider || "duckduckgo");
  }, [searchSettingsQuery.data]);

  if (llmSettingsQuery.isLoading) {
    return <EmptyState title="Loading settings" description="Checking whether a model API has already been configured." />;
  }

  const errorMessage =
    updateLlmSettingsMutation.error instanceof ApiError ? updateLlmSettingsMutation.error.message : null;
  const searchErrorMessage =
    updateSearchSettingsMutation.error instanceof ApiError ? updateSearchSettingsMutation.error.message : null;
  const loadModelsErrorMessage =
    loadModelsMutation.error instanceof ApiError ? loadModelsMutation.error.message : loadModelsMutation.error instanceof Error ? loadModelsMutation.error.message : null;
  const requiresApiKey = !llmSettingsQuery.data?.is_configured;
  const selectedPreset = providerPresets.find((preset) => preset.id === providerName) ?? providerPresets[0];
  const configuredProviderLabel =
    providerPresets.find((preset) => preset.id === (llmSettingsQuery.data?.provider_name ?? ""))?.label
    ?? llmSettingsQuery.data?.provider_name
    ?? "custom";
  const modelOptions = availableModels.length > 0 ? availableModels : selectedPreset.models;
  const isBedrock = providerName === "bedrock";
  const isCustomModel = modelOptions.length === 0 || !modelOptions.includes(chatModel);
  const loadModelsLabel = isBedrock ? "Load Bedrock models" : "Load models";
  const modelFieldLabel = isBedrock ? "Model ID" : "Chat model";
  const modelFieldHelp = isBedrock
    ? "Choose the Bedrock model ID used for routing and grounded answer synthesis. Example: anthropic.claude-3-5-sonnet-20240620-v1:0."
    : "Choose the chat model used for routing and grounded answer synthesis.";

  const handleProviderChange = (nextProviderName: string) => {
    setProviderName(nextProviderName);
    const preset = providerPresets.find((item) => item.id === nextProviderName);
    if (!preset) {
      return;
    }
    if (preset.baseUrl) {
      setBaseUrl(preset.baseUrl);
    }
    setWireApi(preset.wireApi);
    if (preset.defaultRegion) {
      setAwsRegion(preset.defaultRegion);
    }
    if (preset.defaultEmbeddingProvider) {
      setEmbeddingProvider(preset.defaultEmbeddingProvider);
    }
    if (preset.defaultEmbeddingModel) {
      setEmbeddingModel(preset.defaultEmbeddingModel);
    }
    if (preset.defaultVectorStore) {
      setVectorStore(preset.defaultVectorStore);
    }
    setAvailableModels([]);
    if (preset.models.length > 0) {
      setChatModel(preset.models[0]);
    }
  };

  const handleLoadModels = async () => {
    if (!isBedrock && !apiKey.trim()) {
      return;
    }
    if (isBedrock && !awsRegion.trim()) {
      return;
    }
    const response = await loadModelsMutation.mutateAsync({
      provider_name: providerName,
      api_key: apiKey.trim() || undefined,
      base_url: isBedrock ? undefined : baseUrl.trim() || undefined,
      aws_region: isBedrock ? awsRegion.trim() : undefined,
      aws_access_key_id: isBedrock ? awsAccessKeyId.trim() || undefined : undefined,
      aws_secret_access_key: isBedrock ? awsSecretAccessKey.trim() || undefined : undefined,
      aws_session_token: isBedrock ? awsSessionToken.trim() || undefined : undefined,
    });
    setAvailableModels(response.items);
    if (response.items.length > 0) {
      setChatModel((current) => (response.items.includes(current) ? current : response.items[0]));
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (requiresApiKey && !isBedrock && !apiKey.trim()) {
      return;
    }
    if (providerName === "bedrock" && !awsRegion.trim()) {
      return;
    }
    await updateLlmSettingsMutation.mutateAsync({
      api_key: isBedrock ? undefined : apiKey.trim() || undefined,
      provider_name: providerName,
      base_url: isBedrock ? "" : baseUrl.trim(),
      wire_api: isBedrock ? "bedrock" : wireApi.trim(),
      aws_region: isBedrock ? awsRegion.trim() : undefined,
      aws_access_key_id: isBedrock ? awsAccessKeyId.trim() || undefined : undefined,
      aws_secret_access_key: isBedrock ? awsSecretAccessKey.trim() || undefined : undefined,
      aws_session_token: isBedrock ? awsSessionToken.trim() || undefined : undefined,
      embedding_provider: embeddingProvider,
      embedding_model: embeddingModel.trim() || undefined,
      vector_store: vectorStore,
      chat_model: chatModel.trim(),
      router_model: chatModel.trim(),
      answer_model: chatModel.trim(),
      router_provider: "llm",
      answer_provider: "llm",
    });
    setApiKey("");
    setAwsAccessKeyId("");
    setAwsSecretAccessKey("");
    setAwsSessionToken("");
    setSuccessMessage("LLM settings saved. The backend will use this key for future requests.");
  };

  const handleSaveSearchSettings = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (searchEnabled && searchProvider === "tavily" && !searchApiKey.trim() && !searchSettingsQuery.data?.search_api_key_masked) {
      return;
    }
    await updateSearchSettingsMutation.mutateAsync({
      search_enabled: searchEnabled,
      search_provider: searchProvider,
      search_api_key: searchApiKey.trim() || undefined,
    });
    setSearchApiKey("");
    setSearchSuccessMessage("Web search settings saved.");
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <Panel
        title="LLM API setup"
        description="On the first visit, configure the model API here. After that the app reuses the stored key until you intentionally replace it."
      >
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-ink-700">Inference backend</span>
            <select
              value={providerName}
              onChange={(event) => handleProviderChange(event.target.value)}
              className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
            >
              {providerPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
            <p className="mt-2 text-sm text-ink-600">{selectedPreset.description}</p>
            <p className="mt-2 text-sm text-ink-500">
              This selector is only for choosing the model backend or endpoint. Project memory and conversation memory are managed elsewhere in the app.
            </p>
            {selectedPreset.compatibilityNote ? (
              <p className="mt-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-700">{selectedPreset.compatibilityNote}</p>
            ) : null}
          </label>

          {isBedrock ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-ink-100 bg-ink-50 px-4 py-4 text-sm text-ink-700">
                <div className="font-semibold text-ink-900">Amazon Bedrock setup</div>
                <div className="mt-2">
                  1. Enter AWS credentials or rely on the AWS default credential chain.
                </div>
                <div className="mt-1">
                  2. Click <span className="font-semibold">{loadModelsLabel}</span> to fetch available Bedrock models.
                </div>
                <div className="mt-1">
                  3. Pick a Bedrock model ID below. You do not need an OpenAI-style API key or Base URL in Bedrock mode.
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">AWS region</span>
                  <input
                    value={awsRegion}
                    onChange={(event) => setAwsRegion(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                    placeholder="us-east-1"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">AWS access key ID</span>
                  <input
                    value={awsAccessKeyId}
                    onChange={(event) => setAwsAccessKeyId(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                    placeholder={llmSettingsQuery.data?.aws_access_key_id_masked ? "Replace stored access key (optional)" : "AKIA..."}
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">AWS secret access key</span>
                  <input
                    type="password"
                    value={awsSecretAccessKey}
                    onChange={(event) => setAwsSecretAccessKey(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                    placeholder={llmSettingsQuery.data?.aws_secret_access_key_masked ? "Replace stored secret key (optional)" : "AWS secret access key"}
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">AWS session token</span>
                  <input
                    type="password"
                    value={awsSessionToken}
                    onChange={(event) => setAwsSessionToken(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                    placeholder={llmSettingsQuery.data?.aws_session_token_masked ? "Replace stored session token (optional)" : "Optional session token"}
                  />
                </label>
              </div>
            </div>
          ) : (
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">API key</span>
              <input
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                placeholder={llmSettingsQuery.data?.api_key_masked ? "Enter a new key to replace the stored one" : "sk-..."}
              />
            </label>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={handleLoadModels}
              disabled={loadModelsMutation.isPending || (!isBedrock && !apiKey.trim()) || (isBedrock && !awsRegion.trim())}
            >
              {loadModelsMutation.isPending ? "Loading models..." : loadModelsLabel}
            </Button>
            <span className="text-sm text-ink-600">
              {availableModels.length > 0
                ? `${availableModels.length} models loaded from provider`
                : isBedrock
                  ? "Load available Bedrock model IDs for the selected AWS region."
                  : "Load official models for the selected provider."}
            </span>
          </div>

          {!isBedrock ? (
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-ink-700">Base URL</span>
                <input
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-ink-700">Wire API</span>
                <select
                  value={wireApi}
                  onChange={(event) => setWireApi(event.target.value)}
                  className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                >
                  <option value="responses">responses</option>
                  <option value="chat_completions">chat_completions</option>
                </select>
              </label>
            </div>
          ) : (
            <p className="rounded-2xl bg-ink-50 px-4 py-3 text-sm text-ink-600">
              Bedrock uses AWS native APIs for chat and embeddings. Base URL and OpenAI wire format are not used.
            </p>
          )}

          <div className="grid gap-4 md:grid-cols-3">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Embedding provider</span>
              <select
                value={embeddingProvider}
                onChange={(event) => setEmbeddingProvider(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
              >
                <option value="deterministic">deterministic</option>
                <option value="openai">openai</option>
                <option value="bedrock">bedrock</option>
              </select>
            </label>

            <label className="block md:col-span-2">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Embedding model</span>
              <input
                value={embeddingModel}
                onChange={(event) => setEmbeddingModel(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                placeholder={embeddingProvider === "openai" ? "text-embedding-3-large" : "amazon.titan-embed-text-v2:0"}
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Vector store</span>
              <select
                value={vectorStore}
                onChange={(event) => setVectorStore(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
              >
                <option value="qdrant">qdrant</option>
                <option value="local">local</option>
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-ink-700">{modelFieldLabel}</span>
            <p className="mb-3 text-sm text-ink-600">{modelFieldHelp}</p>
            <div className="space-y-3">
              <select
                value={isCustomModel ? "__custom__" : chatModel}
                onChange={(event) => {
                  if (event.target.value === "__custom__") {
                    setChatModel("");
                    return;
                  }
                  setChatModel(event.target.value);
                }}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
              >
                {modelOptions.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
                <option value="__custom__">Custom model name</option>
              </select>
              {isCustomModel ? (
                <input
                  value={chatModel}
                  onChange={(event) => setChatModel(event.target.value)}
                  className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                  placeholder={isBedrock ? "Enter a Bedrock model ID" : "Enter any compatible model name"}
                />
              ) : null}
            </div>
          </label>

          {loadModelsErrorMessage ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{loadModelsErrorMessage}</p> : null}
          {errorMessage ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMessage}</p> : null}
          {successMessage ? <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{successMessage}</p> : null}

          <Button
            type="submit"
            disabled={updateLlmSettingsMutation.isPending || (requiresApiKey && !isBedrock && !apiKey.trim()) || (isBedrock && !awsRegion.trim())}
          >
            {updateLlmSettingsMutation.isPending
              ? "Saving..."
              : llmSettingsQuery.data?.is_configured
                ? "Save LLM settings"
                : isBedrock
                  ? "Save Bedrock settings"
                  : "Save API key"}
          </Button>
        </form>
      </Panel>

      <Panel title="Current configuration" description="The backend stores the active runtime LLM settings and reuses them on subsequent visits.">
        {llmSettingsQuery.data ? (
          <div className="space-y-3 text-sm text-ink-700">
            <div>
              <span className="font-semibold text-ink-900">Configured:</span> {llmSettingsQuery.data.is_configured ? "Yes" : "No"}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Inference backend:</span> {configuredProviderLabel}
            </div>
            {llmSettingsQuery.data.provider_name !== "bedrock" ? (
              <div>
                <span className="font-semibold text-ink-900">Stored key:</span> {llmSettingsQuery.data.api_key_masked ?? "Not configured"}
              </div>
            ) : null}
            {llmSettingsQuery.data.provider_name === "bedrock" ? (
              <>
                <div>
                  <span className="font-semibold text-ink-900">AWS region:</span> {llmSettingsQuery.data.aws_region ?? "Unset"}
                </div>
                <div>
                  <span className="font-semibold text-ink-900">Stored access key:</span>{" "}
                  {llmSettingsQuery.data.aws_access_key_id_masked ?? "Using default AWS credential chain or not configured"}
                </div>
              </>
            ) : (
              <>
                <div>
                  <span className="font-semibold text-ink-900">Base URL:</span> {llmSettingsQuery.data.base_url}
                </div>
                <div>
                  <span className="font-semibold text-ink-900">Wire API:</span> {llmSettingsQuery.data.wire_api}
                </div>
              </>
            )}
            <div>
              <span className="font-semibold text-ink-900">Embedding provider:</span> {llmSettingsQuery.data.embedding_provider}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Embedding model:</span> {llmSettingsQuery.data.embedding_model ?? "Unset"}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Vector store:</span> {llmSettingsQuery.data.vector_store}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Model ID:</span> {llmSettingsQuery.data.chat_model ?? "Unset"}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Router provider:</span> {llmSettingsQuery.data.router_provider}
            </div>
            <div>
              <span className="font-semibold text-ink-900">Answer provider:</span> {llmSettingsQuery.data.answer_provider}
            </div>
          </div>
        ) : (
          <EmptyState title="Settings unavailable" description="Could not load the runtime LLM configuration." />
        )}
      </Panel>

      <Panel title="Web search" description="Web-enabled chat modes use this runtime search configuration. DuckDuckGo works without an API key; Tavily needs one.">
        <form className="space-y-4" onSubmit={handleSaveSearchSettings}>
          <label className="flex items-center gap-3 rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800">
            <input
              type="checkbox"
              checked={searchEnabled}
              onChange={(event) => setSearchEnabled(event.target.checked)}
              className="h-4 w-4 rounded border-ink-300 text-signal-700 focus:ring-signal-500"
            />
            Enable web search
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-ink-700">Search provider</span>
            <select
              value={searchProvider}
              onChange={(event) => setSearchProvider(event.target.value)}
              className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
            >
              <option value="duckduckgo">DuckDuckGo (no key)</option>
              <option value="tavily">Tavily</option>
            </select>
          </label>

          {searchProvider === "tavily" ? (
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Search API key</span>
              <input
                type="password"
                value={searchApiKey}
                onChange={(event) => setSearchApiKey(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                placeholder={searchSettingsQuery.data?.search_api_key_masked ? "Enter a new Tavily key to replace the stored one" : "tvly-..."}
              />
            </label>
          ) : (
            <p className="rounded-2xl bg-ink-50 px-4 py-3 text-sm text-ink-600">
              DuckDuckGo is a lightweight demo provider and does not require a separate API key.
            </p>
          )}

          {searchErrorMessage ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{searchErrorMessage}</p> : null}
          {searchSuccessMessage ? <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{searchSuccessMessage}</p> : null}

          <Button type="submit" disabled={updateSearchSettingsMutation.isPending}>
            {updateSearchSettingsMutation.isPending ? "Saving..." : "Save web search settings"}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
