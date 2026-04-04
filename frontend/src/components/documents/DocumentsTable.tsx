import { useEffect, useState } from "react";

import type { DocumentDetail, DocumentSummary } from "../../types/api";
import { formatDateTime, formatFileSize, getStatusTone } from "../../lib/utils";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type DocumentsTableProps = {
  documents: DocumentSummary[];
  detailMap: Map<string, DocumentDetail | undefined>;
  deletingDocumentId: string | null;
  reindexingDocumentId: string | null;
  renamingDocumentId: string | null;
  onOpenDetail: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  onReindex: (documentId: string) => void;
  onRename: (documentId: string, filename: string) => Promise<unknown>;
};

export function DocumentsTable({
  documents,
  detailMap,
  deletingDocumentId,
  reindexingDocumentId,
  renamingDocumentId,
  onOpenDetail,
  onDelete,
  onReindex,
  onRename,
}: DocumentsTableProps) {
  const [editingDocumentId, setEditingDocumentId] = useState<string | null>(null);
  const [filenameDraft, setFilenameDraft] = useState("");

  useEffect(() => {
    if (editingDocumentId && !documents.some((document) => document.id === editingDocumentId)) {
      setEditingDocumentId(null);
      setFilenameDraft("");
    }
  }, [documents, editingDocumentId]);

  const startRename = (document: DocumentSummary) => {
    setEditingDocumentId(document.id);
    setFilenameDraft(document.filename);
  };

  const cancelRename = () => {
    setEditingDocumentId(null);
    setFilenameDraft("");
  };

  const saveRename = async (documentId: string) => {
    const nextFilename = filenameDraft.trim();
    if (!nextFilename) {
      return;
    }
    await onRename(documentId, nextFilename);
    setEditingDocumentId(null);
    setFilenameDraft("");
  };

  return (
    <div className="overflow-hidden rounded-3xl border border-white/70 bg-white shadow-panel">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-ink-100 text-sm">
          <thead className="bg-ink-50">
            <tr className="text-left text-xs font-semibold uppercase tracking-[0.16em] text-ink-500">
              <th className="px-5 py-4">Document</th>
              <th className="px-5 py-4">Status</th>
              <th className="px-5 py-4">Uploaded</th>
              <th className="px-5 py-4">Chunks</th>
              <th className="px-5 py-4">Size</th>
              <th className="px-5 py-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {documents.map((document) => {
              const detail = detailMap.get(document.id);
              const isEditing = editingDocumentId === document.id;
              const isBusy =
                deletingDocumentId === document.id ||
                reindexingDocumentId === document.id ||
                renamingDocumentId === document.id;

              return (
                <tr key={document.id} className="align-top">
                  <td className="px-5 py-4">
                    <div className="space-y-2">
                      {isEditing ? (
                        <div className="space-y-2">
                          <input
                            value={filenameDraft}
                            onChange={(event) => setFilenameDraft(event.target.value)}
                            className="w-full min-w-[220px] rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-semibold text-ink-900 outline-none focus:border-signal-500"
                          />
                          <p className="text-xs text-ink-500">You can change the display name, but the file extension stays locked.</p>
                        </div>
                      ) : (
                        <div className="font-semibold text-ink-900">{document.filename}</div>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Badge label={document.file_type.toUpperCase()} tone="info" />
                        {document.page_count ? <Badge label={`${document.page_count} pages`} /> : null}
                        {document.slide_count ? <Badge label={`${document.slide_count} slides`} /> : null}
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <Badge label={document.status} tone={getStatusTone(document.status)} />
                  </td>
                  <td className="px-5 py-4 text-ink-600">{formatDateTime(document.created_at)}</td>
                  <td className="px-5 py-4 text-ink-600">{detail ? detail.chunk_count : "..."}</td>
                  <td className="px-5 py-4 text-ink-600">{formatFileSize(document.file_size)}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      {isEditing ? (
                        <>
                          <Button
                            variant="secondary"
                            disabled={renamingDocumentId === document.id || !filenameDraft.trim()}
                            onClick={() => void saveRename(document.id)}
                          >
                            {renamingDocumentId === document.id ? "Saving..." : "Save"}
                          </Button>
                          <Button variant="ghost" disabled={renamingDocumentId === document.id} onClick={cancelRename}>
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variant="secondary" disabled={isBusy} onClick={() => startRename(document)}>
                            Rename
                          </Button>
                          <Button variant="secondary" disabled={isBusy} onClick={() => onOpenDetail(document.id)}>
                            Details
                          </Button>
                          <Button variant="ghost" disabled={isBusy} onClick={() => onReindex(document.id)}>
                            {reindexingDocumentId === document.id ? "Reindexing..." : "Reindex"}
                          </Button>
                          <Button variant="danger" disabled={isBusy} onClick={() => onDelete(document.id)}>
                            {deletingDocumentId === document.id ? "Deleting..." : "Delete"}
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
