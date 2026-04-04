import type { ConversationSummary } from "../../types/api";
import { formatDateTime } from "../../lib/utils";
import { Button } from "../common/Button";
import { Panel } from "../common/Panel";

type ConversationListProps = {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  isStartingFresh: boolean;
  isLoading: boolean;
  deletingConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onStartNewConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
};

export function ConversationList({
  conversations,
  activeConversationId,
  isStartingFresh,
  isLoading,
  deletingConversationId,
  onSelectConversation,
  onStartNewConversation,
  onDeleteConversation,
}: ConversationListProps) {
  return (
    <Panel
      title="Chats"
      description="Start a fresh thread or reopen any saved conversation for this project."
      actions={
        <Button variant="ghost" onClick={onStartNewConversation}>
          New chat
        </Button>
      }
    >
      <div className="space-y-3">
        <button
          type="button"
          onClick={onStartNewConversation}
          className={[
            "w-full rounded-2xl border px-4 py-3 text-left transition",
            isStartingFresh
              ? "border-signal-300 bg-signal-50 text-signal-900"
              : "border-ink-100 bg-ink-50 text-ink-700 hover:border-ink-200 hover:bg-white",
          ].join(" ")}
        >
          <div className="text-sm font-semibold">New chat draft</div>
          <div className="mt-1 text-xs text-ink-500">Start a new conversation without losing older threads.</div>
        </button>

        {isLoading ? <p className="text-sm text-ink-600">Loading saved conversations...</p> : null}

        {!isLoading && conversations.length === 0 ? (
          <p className="text-sm text-ink-600">No saved conversations yet.</p>
        ) : null}

        {!isLoading ? (
          <div className="max-h-72 space-y-2 overflow-auto pr-1 scrollbar-thin">
            {conversations.map((conversation) => {
              const isActive = !isStartingFresh && conversation.id === activeConversationId;
              return (
                <div
                  key={conversation.id}
                  className={[
                    "rounded-2xl border px-4 py-3 transition",
                    isActive
                      ? "border-ink-900 bg-ink-900 text-white"
                      : "border-ink-100 bg-white text-ink-800 hover:border-ink-200 hover:bg-ink-50",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <button type="button" onClick={() => onSelectConversation(conversation.id)} className="min-w-0 flex-1 text-left">
                      <div className="text-sm font-semibold">{conversation.title || "Untitled conversation"}</div>
                      <div className={["mt-1 text-xs", isActive ? "text-ink-200" : "text-ink-500"].join(" ")}>
                        {formatDateTime(conversation.updated_at || conversation.created_at)}
                      </div>
                      <div className={["mt-2 line-clamp-2 text-xs leading-5", isActive ? "text-ink-100" : "text-ink-600"].join(" ")}>
                        {conversation.summary?.trim() || "Saved conversation with grounded answers and citations."}
                      </div>
                    </button>
                    <Button
                      type="button"
                      variant="ghost"
                      className={["px-3 py-2 text-xs", isActive ? "text-ink-200 hover:text-white" : ""].join(" ")}
                      onClick={() => onDeleteConversation(conversation.id)}
                    >
                      {deletingConversationId === conversation.id ? "Deleting..." : "Delete"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
