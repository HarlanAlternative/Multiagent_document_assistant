import type { ConversationDetail, ConversationSummary } from "../types/api";
import { deleteRequest, getJson } from "./client";

export function listConversations(projectId: string): Promise<ConversationSummary[]> {
  return getJson<ConversationSummary[]>(`/conversations?project_id=${encodeURIComponent(projectId)}`);
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(`/conversations/${conversationId}`);
}

export function deleteConversation(projectId: string, conversationId: string): Promise<void> {
  return deleteRequest(`/conversations/${conversationId}?project_id=${encodeURIComponent(projectId)}`);
}
