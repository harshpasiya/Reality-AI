import { apiClient } from "./client";
import type { Listing } from "./listings";

/** A listing in a chat reply: the backend adds how the AI search found it. */
export interface ChatListing extends Listing {
  bhk?: number | null;
  match_note?:
    "exact" | "relaxed_radius" | "relaxed_bhk" | "relaxed_locality" | null;
  distance_score?: number | null;
}

export type { Listing };

export interface ChatMessageRequest {
  conversation_id: number | null;
  message: string;
  polygon: [number, number][] | null;
}

export interface ChatMessageResponse {
  conversation_id: number;
  reply: string;
  listings: ChatListing[];
}

export interface HistoricalMessage {
  /** Client-side key only; the backend does not number messages. */
  id?: string;
  sender: "user" | "assistant";
  message: string;
  timestamp: string;
  listings?: ChatListing[];
  /** Set on a message that failed to send, so the UI can offer a retry. */
  failed?: boolean;
}

export interface ConversationHistoryResponse {
  conversation_id: number;
  user_id: number;
  messages: HistoricalMessage[];
  listings: Listing[];
}

export function sendChatMessage(
  data: ChatMessageRequest,
): Promise<ChatMessageResponse> {
  return apiClient("/chat", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getConversationHistory(
  conversationId: number,
): Promise<ConversationHistoryResponse> {
  return apiClient(`/chat/${conversationId}`, {
    method: "GET",
  });
}
