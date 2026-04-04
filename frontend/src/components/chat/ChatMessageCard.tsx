import { Badge } from "../common/Badge";
import { Panel } from "../common/Panel";
import { CitationList } from "./CitationList";
import { RetrievedChunkList } from "./RetrievedChunkList";
import { WebResultList } from "./WebResultList";
import type { ChatTranscriptItem } from "../../types/ui";
import { formatDateTime, getStatusTone } from "../../lib/utils";

type ChatMessageCardProps = {
  message: ChatTranscriptItem;
};

export function ChatMessageCard({ message }: ChatMessageCardProps) {
  if (message.role === "user") {
    return (
      <Panel className="border-ink-200 bg-ink-900 text-white">
        <div className="flex items-center justify-between gap-4">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-200">User question</span>
          <span className="text-xs text-ink-300">{formatDateTime(message.createdAt)}</span>
        </div>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-white">{message.content}</p>
      </Panel>
    );
  }

  if (message.role === "system") {
    return (
      <Panel className="border-rose-100 bg-rose-50">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">System</span>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-rose-700">{message.content}</p>
      </Panel>
    );
  }

  const restoredCitations = message.citations ?? [];
  const routeUsed = message.response?.route_used ?? message.routeUsed ?? "saved_answer";

  return (
    <Panel className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-signal-700">Assistant answer</span>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-ink-800">{message.response?.answer ?? message.content}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge label={routeUsed} tone={getStatusTone(routeUsed)} />
          <Badge label={formatDateTime(message.createdAt)} />
        </div>
      </div>

      {message.response?.confidence_note ? (
        <div className="rounded-2xl bg-signal-50 px-4 py-3 text-sm text-signal-800">{message.response.confidence_note}</div>
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
    </Panel>
  );
}
