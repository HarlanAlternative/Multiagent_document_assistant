import type { ChatTranscriptItem } from "../../types/ui";
import { formatDateTime, getStatusTone } from "../../lib/utils";
import { Badge } from "../common/Badge";
import { AnswerContent } from "./AnswerContent";
import { CitationList } from "./CitationList";
import { RetrievedChunkList } from "./RetrievedChunkList";
import { WebResultList } from "./WebResultList";

type ChatTurnCardProps = {
  turn: ChatTranscriptItem[];
};

function renderAssistantSection(message: Extract<ChatTranscriptItem, { role: "assistant" }>) {
  const restoredCitations = message.citations ?? [];
  const routeUsed = message.response?.route_used ?? message.routeUsed ?? "saved_answer";
  const sourceScopeNote =
    routeUsed === "private_only"
      ? "This answer used only uploaded documents from the current project."
      : routeUsed === "web_only"
        ? "This answer used only external web results."
        : routeUsed === "private_plus_web"
          ? "This answer combined uploaded documents with external web results."
          : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 flex-1">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-signal-700">Assistant answer</span>
          <div className="mt-3">
            <AnswerContent text={message.response?.answer ?? message.content} />
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Badge label={routeUsed} tone={getStatusTone(routeUsed)} />
          <Badge label={formatDateTime(message.createdAt)} />
        </div>
      </div>

      {message.response?.confidence_note ? (
        <div className="rounded-2xl bg-signal-50 px-4 py-3 text-sm text-signal-800">{message.response.confidence_note}</div>
      ) : null}

      {sourceScopeNote ? (
        <div className="rounded-2xl border border-ink-100 bg-ink-50 px-4 py-3 text-sm text-ink-700">{sourceScopeNote}</div>
      ) : null}

      {message.response && message.response.retrieved_chunks.length === 0 && message.response.web_results.length === 0 ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No relevant information found in selected documents.
        </div>
      ) : null}

      {message.response ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-ink-900">Internal sources</h3>
            <CitationList citations={message.response.internal_sources} emptyMessage="No internal citations returned." />
          </div>
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-ink-900">External sources</h3>
            <CitationList citations={message.response.external_sources} emptyMessage="No external citations returned." />
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-ink-900">Saved citations</h3>
          <CitationList citations={restoredCitations} emptyMessage="No saved citations for this historical answer." />
        </div>
      )}

      {message.response && message.response.route_used !== "web_only" ? (
        <details className="rounded-2xl border border-ink-100 bg-ink-50 p-4" open>
          <summary className="cursor-pointer text-sm font-semibold text-ink-800">Retrieved document evidence</summary>
          <div className="mt-4">
            <RetrievedChunkList chunks={message.response.retrieved_chunks} />
          </div>
        </details>
      ) : null}

      {message.response && message.response.web_results.length > 0 ? (
        <details className="rounded-2xl border border-ink-100 bg-ink-50 p-4" open>
          <summary className="cursor-pointer text-sm font-semibold text-ink-800">Web search evidence</summary>
          <div className="mt-4">
            <WebResultList results={message.response.web_results} />
          </div>
        </details>
      ) : null}
    </div>
  );
}

function renderSystemSection(message: Extract<ChatTranscriptItem, { role: "system" }>) {
  return (
    <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-4">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">System</span>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-rose-700">{message.content}</p>
    </div>
  );
}

export function ChatTurnCard({ turn }: ChatTurnCardProps) {
  const userMessage = turn.find((message): message is Extract<ChatTranscriptItem, { role: "user" }> => message.role === "user");
  const followUps = turn.filter((message) => message.role !== "user");

  return (
    <article className="overflow-hidden rounded-3xl border border-white/70 bg-white/90 shadow-panel">
      {userMessage ? (
        <div className="border-b border-ink-900/10 bg-ink-900 px-6 py-5 text-white">
          <div className="flex items-center justify-between gap-4">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-200">User question</span>
            <span className="text-xs text-ink-200">{formatDateTime(userMessage.createdAt)}</span>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-white">{userMessage.content}</p>
        </div>
      ) : null}

      <div className="space-y-6 px-6 py-5">
        {followUps.length === 0 ? (
          <p className="text-sm text-ink-500">Waiting for an answer...</p>
        ) : (
          followUps.map((message, index) => (
            <div key={message.id} className={index > 0 ? "border-t border-ink-100 pt-6" : ""}>
              {message.role === "assistant" ? renderAssistantSection(message) : renderSystemSection(message)}
            </div>
          ))
        )}
      </div>
    </article>
  );
}
