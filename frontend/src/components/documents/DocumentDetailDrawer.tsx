import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import type { DocumentDetail } from "../../types/api";
import { formatDateTime, formatFileSize, getStatusTone } from "../../lib/utils";

type DocumentDetailDrawerProps = {
  document: DocumentDetail | null;
  onClose: () => void;
};

export function DocumentDetailDrawer({ document, onClose }: DocumentDetailDrawerProps) {
  if (!document) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-900/20 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-3xl border border-white/70 bg-white p-6 shadow-panel">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-ink-900">{document.filename}</h3>
            <p className="mt-1 text-sm text-ink-600">Detailed ingestion metadata and source storage information.</p>
          </div>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge label={document.file_type.toUpperCase()} tone="info" />
          <Badge label={document.status} tone={getStatusTone(document.status)} />
        </div>

        <dl className="mt-6 space-y-4 text-sm">
          <div>
            <dt className="font-semibold text-ink-700">Uploaded</dt>
            <dd className="mt-1 text-ink-600">{formatDateTime(document.created_at)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-700">File size</dt>
            <dd className="mt-1 text-ink-600">{formatFileSize(document.file_size)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-700">Chunk count</dt>
            <dd className="mt-1 text-ink-600">{document.chunk_count}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-700">Source units</dt>
            <dd className="mt-1 text-ink-600">
              {document.page_count ? `${document.page_count} pages` : document.slide_count ? `${document.slide_count} slides` : "Unknown"}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-700">Checksum</dt>
            <dd className="mt-1 break-all text-ink-600">{document.checksum}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink-700">Storage path</dt>
            <dd className="mt-1 break-all text-ink-600">{document.storage_path}</dd>
          </div>
          {document.error_message ? (
            <div>
              <dt className="font-semibold text-rose-700">Error</dt>
              <dd className="mt-1 text-rose-600">{document.error_message}</dd>
            </div>
          ) : null}
        </dl>
      </div>
    </div>
  );
}
