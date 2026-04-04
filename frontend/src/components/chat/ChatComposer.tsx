import type { FormEvent } from "react";

import type { ChatMode, DocumentSummary } from "../../types/api";
import { Button } from "../common/Button";
import { Panel } from "../common/Panel";
import { Spinner } from "../common/Spinner";

const modes: Array<{ value: ChatMode; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "private_only", label: "Private docs only" },
  { value: "private_plus_web", label: "Private docs + web" },
  { value: "web_only", label: "Web only" },
];

type ChatComposerProps = {
  documents: DocumentSummary[];
  projectName: string | null;
  question: string;
  mode: ChatMode;
  fileType: string;
  selectedDocumentIds: string[];
  isLoading: boolean;
  errorMessage: string | null;
  onQuestionChange: (value: string) => void;
  onModeChange: (value: ChatMode) => void;
  onFileTypeChange: (value: string) => void;
  onToggleDocument: (documentId: string) => void;
  onSelectAllDocuments: () => void;
  onClearDocumentSelection: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onStartNewConversation: () => void;
};

export function ChatComposer({
  documents,
  projectName,
  question,
  mode,
  fileType,
  selectedDocumentIds,
  isLoading,
  errorMessage,
  onQuestionChange,
  onModeChange,
  onFileTypeChange,
  onToggleDocument,
  onSelectAllDocuments,
  onClearDocumentSelection,
  onSubmit,
  onStartNewConversation,
}: ChatComposerProps) {
  const allDocumentsSelected = documents.length > 0 && selectedDocumentIds.length === documents.length;
  const isWebOnly = mode === "web_only";
  const documentScopeLabel = isWebOnly
    ? "web only"
    : selectedDocumentIds.length === 0
      ? "all docs"
      : `${selectedDocumentIds.length} selected`;

  return (
    <div className="space-y-5">
      <Panel
        title="Ask the knowledge base"
        description={`Route questions through the current backend QA workflow${projectName ? ` for ${projectName}` : ""} and inspect route, citations, and retrieved evidence.`}
        actions={
          <Button variant="ghost" onClick={onStartNewConversation}>
            New chat
          </Button>
        }
      >
        <form className="space-y-4" onSubmit={onSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-ink-700">Question</span>
            <textarea
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              placeholder="Ask a question grounded in your uploaded documents."
              disabled={!projectName}
              rows={5}
              className="w-full rounded-2xl border border-ink-200 bg-ink-50 px-4 py-3 text-sm text-ink-800 outline-none placeholder:text-ink-400 focus:border-signal-500"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Mode</span>
              <select
                value={mode}
                onChange={(event) => onModeChange(event.target.value as ChatMode)}
                disabled={!projectName}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
              >
                {modes.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">File type filter</span>
              <select
                value={fileType}
                onChange={(event) => onFileTypeChange(event.target.value)}
                disabled={!projectName || isWebOnly}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
              >
                <option value="">All document types</option>
                <option value="pdf">PDF only</option>
                <option value="pptx">PPTX only</option>
                <option value="docx">DOCX only</option>
                <option value="txt">TXT only</option>
                <option value="md">Markdown only</option>
              </select>
              {isWebOnly ? <p className="mt-2 text-xs text-ink-500">File type filtering is ignored in web-only mode.</p> : null}
            </label>
          </div>

          {isWebOnly ? (
            <div className="rounded-2xl border border-ink-100 bg-ink-50 p-4 text-sm text-ink-600">
              Web-only mode ignores uploaded-document scope and file filters. The answer will only use external web results.
            </div>
          ) : (
            <div className="rounded-2xl border border-ink-100 bg-ink-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-ink-800">Optional document scope</h3>
                  <p className="mt-1 text-xs text-ink-600">
                    {selectedDocumentIds.length === 0
                      ? "No explicit document filter is applied. Private retrieval will search across all indexed documents in this project."
                      : "Restrict retrieval to selected documents for tighter demos."}
                  </p>
                </div>
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">{documentScopeLabel}</span>
              </div>

              {documents.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="px-3 py-2 text-xs"
                    onClick={onSelectAllDocuments}
                    disabled={!projectName || allDocumentsSelected}
                  >
                    Select all
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="px-3 py-2 text-xs"
                    onClick={onClearDocumentSelection}
                    disabled={!projectName || selectedDocumentIds.length === 0}
                  >
                    Clear selection
                  </Button>
                </div>
              ) : null}

              <div className="mt-4 max-h-52 space-y-2 overflow-auto pr-1 scrollbar-thin">
                {documents.length === 0 ? (
                  <p className="text-sm text-ink-500">Upload documents first to enable scoped retrieval.</p>
                ) : (
                  documents.map((document) => (
                    <label
                      key={document.id}
                      className="flex cursor-pointer items-center gap-3 rounded-2xl border border-transparent bg-white px-3 py-2.5 hover:border-ink-200"
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocumentIds.includes(document.id)}
                        onChange={() => onToggleDocument(document.id)}
                        disabled={!projectName}
                        className="h-4 w-4 rounded border-ink-300 text-signal-700 focus:ring-signal-500"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-ink-800">{document.filename}</div>
                        <div className="text-xs text-ink-500">{document.file_type.toUpperCase()}</div>
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>
          )}

          {mode !== "private_only" ? (
            <p className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Web-enabled modes use the configured search provider when available and gracefully fall back if search is unavailable.
            </p>
          ) : null}

          {errorMessage ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMessage}</p> : null}

          {!projectName ? (
            <p className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Create or select a project before starting a chat session.
            </p>
          ) : null}

          <Button type="submit" fullWidth disabled={!projectName || isLoading || question.trim().length < 3}>
            {isLoading ? (
              <span className="flex items-center gap-2">
                <Spinner />
                Asking...
              </span>
            ) : (
              "Ask question"
            )}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
