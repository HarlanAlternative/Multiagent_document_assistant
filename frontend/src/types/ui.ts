import type { ChatAskResponse, ChatMode } from "./api";

export type ChatTranscriptItem =
  | {
      id: string;
      role: "user";
      content: string;
      createdAt: string;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      createdAt: string;
      response?: ChatAskResponse;
      routeUsed?: string | null;
      citations?: ChatAskResponse["citations"];
    }
  | {
      id: string;
      role: "system";
      content: string;
      createdAt: string;
    };

export type ChatDraftState = {
  question: string;
  mode: ChatMode;
  fileType: string;
  selectedDocumentIds: string[];
};
