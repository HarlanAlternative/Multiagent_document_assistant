export type HealthStatus = {
  status: string;
  app_name: string;
  vector_store: string;
  embedding_provider: string;
  router_provider?: string;
  answer_provider?: string;
  chat_model?: string | null;
  llm_configured?: boolean;
  search_enabled?: boolean;
  search_provider?: string;
  project_count?: number;
};

export type DocumentSummary = {
  id: string;
  project_id: string | null;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
  checksum: string;
  page_count: number | null;
  slide_count: number | null;
  created_at: string;
  updated_at: string | null;
};

export type DocumentDetail = DocumentSummary & {
  storage_path: string;
  error_message: string | null;
  chunk_count: number;
};

export type DocumentListResponse = {
  items: DocumentSummary[];
};

export type DocumentUploadResponse = {
  document_id: string;
  project_id: string | null;
  filename: string;
  status: string;
};

export type DocumentRenameRequest = {
  filename: string;
};

export type ChatMode = "auto" | "private_only" | "private_plus_web" | "web_only";

export type Citation = {
  source_kind: string;
  document_id: string | null;
  chunk_id: string | null;
  title: string;
  page_number: number | null;
  slide_number: number | null;
  url: string | null;
};

export type RetrievedChunk = {
  chunk_id: string;
  document_id: string;
  filename: string;
  score: number;
  content: string;
  content_preview: string;
  page_number: number | null;
  slide_number: number | null;
};

export type WebSearchResult = {
  title: string;
  url: string;
  snippet: string;
  source: string;
  rank: number;
};

export type ChatAskRequest = {
  project_id: string | null;
  question: string;
  mode: ChatMode;
  selected_document_ids: string[];
  file_type: string | null;
  conversation_id: string | null;
};

export type ChatAskResponse = {
  answer: string;
  citations: Citation[];
  route_used: string;
  project_id: string;
  conversation_id: string;
  retrieved_chunks: RetrievedChunk[];
  web_results: WebSearchResult[];
  confidence_note: string | null;
  internal_sources: Citation[];
  external_sources: Citation[];
  project_memory: string | null;
  created_at: string;
};

export type ConversationMessage = {
  id: string;
  role: string;
  content: string;
  route_used: string | null;
  created_at: string;
  citations: Citation[];
};

export type ConversationSummary = {
  id: string;
  project_id: string | null;
  title: string;
  summary: string | null;
  created_at: string;
  updated_at: string | null;
};

export type ConversationDetail = ConversationSummary & {
  messages: ConversationMessage[];
};

export type Project = {
  id: string;
  name: string;
  description: string | null;
  memory: string | null;
  created_at: string;
  updated_at: string | null;
};

export type ProjectListResponse = {
  items: Project[];
};

export type ProjectCreateRequest = {
  name: string;
  description?: string | null;
  memory?: string | null;
};

export type ProjectUpdateRequest = {
  name?: string | null;
  description?: string | null;
  memory?: string | null;
};

export type ProjectReindexResponse = {
  project_id: string;
  reindexed_document_ids: string[];
  failed_documents: string[];
};

export type LlmSettings = {
  is_configured: boolean;
  provider_name: string | null;
  api_key_masked: string | null;
  base_url: string;
  wire_api: string;
  aws_region: string | null;
  aws_access_key_id_masked: string | null;
  aws_secret_access_key_masked: string | null;
  aws_session_token_masked: string | null;
  embedding_provider: string;
  embedding_model: string | null;
  vector_store: string;
  chat_model: string | null;
  router_model: string | null;
  answer_model: string | null;
  router_provider: string;
  answer_provider: string;
};

export type LlmSettingsUpdateRequest = {
  api_key?: string | null;
  provider_name?: string | null;
  base_url?: string | null;
  wire_api?: string | null;
  aws_region?: string | null;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
  aws_session_token?: string | null;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  vector_store?: string | null;
  chat_model?: string | null;
  router_model?: string | null;
  answer_model?: string | null;
  router_provider?: string | null;
  answer_provider?: string | null;
};

export type SearchSettings = {
  search_enabled: boolean;
  search_provider: string;
  search_api_key_masked: string | null;
};

export type SearchSettingsUpdateRequest = {
  search_enabled?: boolean;
  search_provider?: string | null;
  search_api_key?: string | null;
};

export type ModelCatalogRequest = {
    provider_name: string;
    api_key?: string | null;
    base_url?: string | null;
    aws_region?: string | null;
    aws_access_key_id?: string | null;
    aws_secret_access_key?: string | null;
    aws_session_token?: string | null;
  };

export type ModelCatalogResponse = {
  items: string[];
};
