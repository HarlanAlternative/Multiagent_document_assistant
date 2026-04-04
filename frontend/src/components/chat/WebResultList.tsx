import type { WebSearchResult } from "../../types/api";
import { Badge } from "../common/Badge";

type WebResultListProps = {
  results: WebSearchResult[];
};

export function WebResultList({ results }: WebResultListProps) {
  if (results.length === 0) {
    return <p className="text-sm text-ink-500">No external web results returned.</p>;
  }

  return (
    <div className="space-y-3">
      {results.map((result) => (
        <article key={`${result.rank}-${result.url}`} className="rounded-2xl border border-ink-100 bg-white px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <a
              className="text-sm font-semibold text-signal-800 underline decoration-signal-300 underline-offset-4"
              href={result.url}
              target="_blank"
              rel="noreferrer"
            >
              {result.title}
            </a>
            <Badge label={`Rank ${result.rank}`} />
            <Badge label={result.source} tone="info" />
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-600">{result.snippet || result.url}</p>
        </article>
      ))}
    </div>
  );
}
