import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { ChatComposer } from "../components/chat/ChatComposer";
import { ChatTurnCard } from "../components/chat/ChatTurnCard";
import { ConversationList } from "../components/chat/ConversationList";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { useWorkspace } from "../components/layout/WorkspaceProvider";
import { useChat } from "../hooks/useChat";
import { useConversations } from "../hooks/useConversations";
import { useDocuments } from "../hooks/useDocuments";
import type { ChatMode, ConversationDetail } from "../types/api";
import type { ChatDraftState, ChatTranscriptItem } from "../types/ui";

const NEW_CHAT_SENTINEL = "__new__";

const initialDraftState: ChatDraftState = {
  question: "",
  mode: "private_only",
  fileType: "",
  selectedDocumentIds: [],
};

function getConversationStorageKey(projectId: string) {
  return `knowledge-copilot.conversation.${projectId}`;
}

function mapConversationToTranscript(conversation: ConversationDetail): ChatTranscriptItem[] {
  return conversation.messages.map((message) => {
    if (message.role === "user") {
      return {
        id: message.id,
        role: "user",
        content: message.content,
        createdAt: message.created_at,
      };
    }

    if (message.role === "assistant") {
      return {
        id: message.id,
        role: "assistant",
        content: message.content,
        createdAt: message.created_at,
        routeUsed: message.route_used,
        citations: message.citations,
      };
    }

    return {
      id: message.id,
      role: "system",
      content: message.content,
      createdAt: message.created_at,
    };
  });
}

function buildLiveContextPreview(messages: ChatTranscriptItem[]): string | null {
  const recentMessages = messages.slice(-4);
  if (recentMessages.length === 0) {
    return null;
  }

  return recentMessages
    .map((message) => {
      const label = message.role === "user" ? "User" : message.role === "assistant" ? "Assistant" : "System";
      const content = message.content.trim();
      const preview = content.length > 220 ? `${content.slice(0, 217).trimEnd()}...` : content;
      return `${label}: ${preview}`;
    })
    .join("\n\n");
}

export function ChatPage() {
  const { currentProject } = useWorkspace();
  const { documentsQuery } = useDocuments(currentProject?.id ?? null);
  const chatMutation = useChat();
  const [draft, setDraft] = useState<ChatDraftState>(initialDraftState);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatTranscriptItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { listQuery: conversationsQuery, detailQuery: conversationDetailQuery, deleteMutation: deleteConversationMutation } = useConversations(
    currentProject?.id ?? null,
    conversationId,
  );

  const documents = documentsQuery.data?.items ?? [];
  const canAsk = useMemo(() => draft.question.trim().length >= 3, [draft.question]);
  const activeSummary = conversationId ? conversationDetailQuery.data?.summary?.trim() || null : null;
  const liveContextPreview = useMemo(() => buildLiveContextPreview(messages), [messages]);
  const sortedConversations = useMemo(
    () =>
      [...(conversationsQuery.data ?? [])].sort((left, right) =>
        (right.updated_at || right.created_at).localeCompare(left.updated_at || left.created_at),
      ),
    [conversationsQuery.data],
  );
  const orderedTurns = useMemo(() => {
    const chronological = [...messages].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
    const turns: ChatTranscriptItem[][] = [];
    let currentTurn: ChatTranscriptItem[] = [];

    chronological.forEach((message) => {
      if (message.role === "user") {
        if (currentTurn.length > 0) {
          turns.push(currentTurn);
        }
        currentTurn = [message];
        return;
      }

      if (currentTurn.length === 0) {
        currentTurn = [message];
        return;
      }

      currentTurn.push(message);
    });

    if (currentTurn.length > 0) {
      turns.push(currentTurn);
    }

    return turns.sort((left, right) => {
      const leftTimestamp = left[left.length - 1]?.createdAt ?? left[0]?.createdAt ?? "";
      const rightTimestamp = right[right.length - 1]?.createdAt ?? right[0]?.createdAt ?? "";
      return rightTimestamp.localeCompare(leftTimestamp);
    });
  }, [messages]);
  const isStartingFresh = conversationId === null;

  useEffect(() => {
    setMessages([]);
    setErrorMessage(null);
    if (!currentProject) {
      setConversationId(null);
      return;
    }

    const stored = localStorage.getItem(getConversationStorageKey(currentProject.id));
    if (stored && stored !== NEW_CHAT_SENTINEL) {
      setConversationId(stored);
      return;
    }
    setConversationId(null);
  }, [currentProject?.id]);

  useEffect(() => {
    if (!currentProject || !conversationsQuery.data) {
      return;
    }

    const storageKey = getConversationStorageKey(currentProject.id);
    const stored = localStorage.getItem(storageKey);
    if (stored === NEW_CHAT_SENTINEL) {
      return;
    }

    const storedExists = stored ? conversationsQuery.data.some((conversation) => conversation.id === stored) : false;
    const nextId = storedExists ? stored : conversationsQuery.data[0]?.id ?? null;
    if (!nextId || nextId === conversationId) {
      return;
    }

    setConversationId(nextId);
    localStorage.setItem(storageKey, nextId);
  }, [currentProject?.id, conversationId, conversationsQuery.data]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    if (!conversationDetailQuery.data) {
      return;
    }
    setMessages(mapConversationToTranscript(conversationDetailQuery.data));
  }, [conversationDetailQuery.data, conversationId]);

  useEffect(() => {
    if (draft.mode !== "web_only") {
      return;
    }
    if (!draft.fileType && draft.selectedDocumentIds.length === 0) {
      return;
    }
    setDraft((current) => ({
      ...current,
      fileType: "",
      selectedDocumentIds: [],
    }));
  }, [draft.mode, draft.fileType, draft.selectedDocumentIds.length]);

  const toggleDocument = (documentId: string) => {
    setDraft((current) => ({
      ...current,
      selectedDocumentIds: current.selectedDocumentIds.includes(documentId)
        ? current.selectedDocumentIds.filter((id) => id !== documentId)
        : [...current.selectedDocumentIds, documentId],
    }));
  };

  const selectAllDocuments = () => {
    setDraft((current) => ({
      ...current,
      selectedDocumentIds: documents.map((document) => document.id),
    }));
  };

  const clearDocumentSelection = () => {
    setDraft((current) => ({
      ...current,
      selectedDocumentIds: [],
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canAsk || chatMutation.isPending) {
      return;
    }

    const question = draft.question.trim();
    setMessages((current) => [
      ...current,
      {
        id: `user-${crypto.randomUUID()}`,
        role: "user",
        content: question,
        createdAt: new Date().toISOString(),
      },
    ]);
    setErrorMessage(null);

    try {
      const response = await chatMutation.mutateAsync({
        project_id: currentProject?.id ?? null,
        question,
        mode: draft.mode,
        selected_document_ids: draft.selectedDocumentIds,
        file_type: draft.fileType || null,
        conversation_id: conversationId,
      });

      setConversationId(response.conversation_id);
      if (currentProject) {
        localStorage.setItem(getConversationStorageKey(currentProject.id), response.conversation_id);
      }
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${response.conversation_id}-${response.created_at}`,
          role: "assistant",
          content: response.answer,
          createdAt: response.created_at,
          response,
        },
      ]);
      setDraft((current) => ({ ...current, question: "" }));
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Unable to get a response from the backend.";
      setErrorMessage(message);
      setMessages((current) => [
        ...current,
        {
          id: `system-${crypto.randomUUID()}`,
          role: "system",
          content: message,
          createdAt: new Date().toISOString(),
        },
      ]);
    }
  };

  const startNewConversation = () => {
    if (currentProject) {
      localStorage.setItem(getConversationStorageKey(currentProject.id), NEW_CHAT_SENTINEL);
    }
    setConversationId(null);
    setMessages([]);
    setErrorMessage(null);
    setDraft((current) => ({ ...current, question: "" }));
  };

  const selectConversation = (nextConversationId: string) => {
    if (currentProject) {
      localStorage.setItem(getConversationStorageKey(currentProject.id), nextConversationId);
    }
    setConversationId(nextConversationId);
    setMessages([]);
    setErrorMessage(null);
  };

  const handleDeleteConversation = async (targetConversationId: string) => {
    if (!currentProject) {
      return;
    }
    const targetConversation = sortedConversations.find((conversation) => conversation.id === targetConversationId);
    const confirmed = window.confirm(
      `Delete conversation "${targetConversation?.title || "Untitled conversation"}"? This only removes the chat thread.`,
    );
    if (!confirmed) {
      return;
    }

    const fallbackConversation = sortedConversations.find((conversation) => conversation.id !== targetConversationId) ?? null;
    await deleteConversationMutation.mutateAsync(targetConversationId);

    if (conversationId === targetConversationId) {
      const nextConversationId = fallbackConversation?.id ?? null;
      if (nextConversationId) {
        localStorage.setItem(getConversationStorageKey(currentProject.id), nextConversationId);
        setConversationId(nextConversationId);
      } else {
        localStorage.setItem(getConversationStorageKey(currentProject.id), NEW_CHAT_SENTINEL);
        setConversationId(null);
      }
      setMessages([]);
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[240px_minmax(0,1.7fr)_minmax(280px,0.78fr)] 2xl:grid-cols-[240px_minmax(0,1.9fr)_320px]">
      <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
        <ConversationList
          conversations={sortedConversations}
          activeConversationId={conversationId}
          isStartingFresh={isStartingFresh}
          isLoading={conversationsQuery.isLoading}
          deletingConversationId={deleteConversationMutation.variables ?? null}
          onSelectConversation={selectConversation}
          onStartNewConversation={startNewConversation}
          onDeleteConversation={(targetConversationId) => void handleDeleteConversation(targetConversationId)}
        />
      </aside>

      <section className="min-w-0 space-y-4">
        <Panel
          title="Conversation"
          description={`This thread is saved for the current project and restored automatically${currentProject ? ` for ${currentProject.name}` : ""}.`}
        >
          {conversationDetailQuery.isLoading && messages.length === 0 ? (
            <p className="text-sm text-ink-600">Loading saved conversation...</p>
          ) : messages.length === 0 ? (
            <EmptyState
              title="No questions yet"
              description="Ask about your uploaded files to see grounded answers, saved citations, and persistent conversation context."
            />
          ) : (
            <div className="space-y-4">
              {orderedTurns.map((turn) => (
                <ChatTurnCard key={turn.map((message) => message.id).join("-")} turn={turn} />
              ))}
            </div>
          )}
        </Panel>
      </section>

      <aside className="min-w-0 space-y-6">
        <ChatComposer
          documents={documents}
          projectName={currentProject?.name ?? null}
          question={draft.question}
          mode={draft.mode}
          fileType={draft.fileType}
          selectedDocumentIds={draft.selectedDocumentIds}
          isLoading={chatMutation.isPending}
          errorMessage={errorMessage}
          onQuestionChange={(question) => setDraft((current) => ({ ...current, question }))}
          onModeChange={(mode: ChatMode) => setDraft((current) => ({ ...current, mode }))}
          onFileTypeChange={(fileType) => setDraft((current) => ({ ...current, fileType }))}
          onToggleDocument={toggleDocument}
          onSelectAllDocuments={selectAllDocuments}
          onClearDocumentSelection={clearDocumentSelection}
          onSubmit={handleSubmit}
          onStartNewConversation={startNewConversation}
        />

        <Panel
          title="Project context"
          description="Retrieval scope and persistent memory both come from the currently selected project."
        >
          {!currentProject ? (
            <p className="text-sm text-ink-600">Create or select a project to start a scoped conversation.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-2xl border border-ink-100 bg-ink-50 px-4 py-3">
                <div className="text-sm font-semibold text-ink-800">{currentProject.name}</div>
                <div className="mt-1 text-sm text-ink-600">
                  {currentProject.description || "No project description yet."}
                </div>
              </div>

              <div className="rounded-2xl border border-ink-100 bg-white px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-ink-800">Conversation memory</h3>
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-400">
                    {activeSummary ? "Compressed" : "Live context"}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-ink-600">
                  {activeSummary ||
                    liveContextPreview ||
                    "Recent turns still fit in the live context window. Compression summary will appear automatically when the thread grows."}
                </p>
              </div>

              <div className="rounded-2xl border border-ink-100 bg-white px-4 py-4">
                <h3 className="text-sm font-semibold text-ink-800">Project memory</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-ink-600">
                  {currentProject.memory?.trim() || "No persistent project notes yet."}
                </p>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Available documents" description="Current retrieval scope is based on documents already indexed for this project.">
          {documentsQuery.isLoading ? (
            <p className="text-sm text-ink-600">Loading indexed documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-ink-600">Upload a document on the Documents page to start a grounded chat session.</p>
          ) : (
            <div className="space-y-3">
              {documents.map((document) => (
                <div key={document.id} className="rounded-2xl border border-ink-100 bg-ink-50 px-4 py-3">
                  <div className="font-medium text-ink-900">{document.filename}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.16em] text-ink-500">{document.file_type}</div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </aside>
    </div>
  );
}
