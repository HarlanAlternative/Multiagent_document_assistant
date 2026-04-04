import { Badge } from "../common/Badge";
import type { RetrievedChunk } from "../../types/api";

type RetrievedChunkListProps = {
  chunks: RetrievedChunk[];
};

export function RetrievedChunkList({ chunks }: RetrievedChunkListProps) {
  if (chunks.length === 0) {
    return <p className="text-sm text-ink-500">No relevant information found in selected documents.</p>;
  }

  return (
    <div className="space-y-3">
      {chunks.map((chunk) => (
        <article key={chunk.chunk_id} className="rounded-2xl border border-ink-100 bg-white px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink-900">{chunk.filename}</span>
            {chunk.page_number ? <Badge label={`Page ${chunk.page_number}`} /> : null}
            {chunk.slide_number ? <Badge label={`Slide ${chunk.slide_number}`} /> : null}
            <Badge label={`Score ${chunk.score.toFixed(3)}`} tone="info" />
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-600">{chunk.content_preview}</p>
        </article>
      ))}
    </div>
  );
}
