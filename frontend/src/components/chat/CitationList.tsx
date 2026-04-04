import type { Citation } from "../../types/api";
import { formatCitation } from "../../lib/utils";

type CitationListProps = {
  citations: Citation[];
  emptyMessage?: string;
};

export function CitationList({ citations, emptyMessage = "No citations returned." }: CitationListProps) {
  if (citations.length === 0) {
    return <p className="text-sm text-ink-500">{emptyMessage}</p>;
  }

  return (
    <ul className="space-y-2">
      {citations.map((citation) => (
        <li
          key={`${citation.chunk_id ?? citation.title}-${citation.page_number ?? citation.slide_number ?? citation.url ?? "source"}`}
          className="rounded-2xl border border-ink-100 bg-ink-50 px-3 py-2 text-sm text-ink-700"
        >
          {citation.url ? (
            <a
              className="font-medium text-signal-800 underline decoration-signal-300 underline-offset-4"
              href={citation.url}
              target="_blank"
              rel="noreferrer"
            >
              {formatCitation(citation)}
            </a>
          ) : (
            formatCitation(citation)
          )}
        </li>
      ))}
    </ul>
  );
}
