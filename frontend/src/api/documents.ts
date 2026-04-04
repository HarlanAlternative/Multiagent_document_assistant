import type { DocumentDetail, DocumentListResponse, DocumentRenameRequest, DocumentSummary, DocumentUploadResponse } from "../types/api";
import { deleteRequest, getJson, patchJson, postFormData, postJson } from "./client";

export function listDocuments(projectId: string): Promise<DocumentListResponse> {
  return getJson<DocumentListResponse>(`/documents?project_id=${encodeURIComponent(projectId)}`);
}

export function getDocument(documentId: string, projectId: string): Promise<DocumentDetail> {
  return getJson<DocumentDetail>(`/documents/${documentId}?project_id=${encodeURIComponent(projectId)}`);
}

export function uploadDocument(projectId: string, file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("project_id", projectId);
  formData.append("file", file);
  return postFormData<DocumentUploadResponse>("/documents/upload", formData);
}

export function deleteDocument(projectId: string, documentId: string): Promise<void> {
  return deleteRequest(`/documents/${documentId}?project_id=${encodeURIComponent(projectId)}`);
}

export function reindexDocument(projectId: string, documentId: string): Promise<DocumentUploadResponse> {
  return postJson<DocumentUploadResponse, Record<string, never>>(
    `/documents/${documentId}/reindex?project_id=${encodeURIComponent(projectId)}`,
    {},
  );
}

export function renameDocument(projectId: string, documentId: string, payload: DocumentRenameRequest): Promise<DocumentSummary> {
  return patchJson<DocumentSummary, DocumentRenameRequest>(
    `/documents/${documentId}?project_id=${encodeURIComponent(projectId)}`,
    payload,
  );
}
