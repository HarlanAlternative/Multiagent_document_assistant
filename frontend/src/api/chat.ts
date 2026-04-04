import type { ChatAskRequest, ChatAskResponse } from "../types/api";
import { postJson } from "./client";

export function askQuestion(payload: ChatAskRequest): Promise<ChatAskResponse> {
  return postJson<ChatAskResponse, ChatAskRequest>("/chat/ask", payload);
}
