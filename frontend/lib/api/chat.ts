import { apiClient } from "./client";

export interface Listing {
  id: number;
  title: string;
  description: string;
  price: number;
  property_type: string;
  carpet_area?: number | null;
  built_up_area?: number | null;
  plot_area?: number | null;
  floor_number?: number | null;
  rooms: {
    bedrooms: number;
    bathrooms: number;
    balconies?: number;
  };
  lat: number;
  lng: number;
  broker_id: number;
  amenities: Record<string, boolean>;
  created_at: string;
  images?: string[] | null;
  video_tour_url?: string | null;
}

export interface ChatMessageRequest {
  conversation_id: string | null;
  message: string;
  polygon: [number, number][] | null;
}

export interface ChatMessageResponse {
  conversation_id: string;
  reply: string;
  listings: Listing[];
}

export interface HistoricalMessage {
  id: string;
  sender: "user" | "assistant";
  message: string;
  created_at: string;
  listings?: Listing[];
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  messages: HistoricalMessage[];
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
  conversationId: string,
): Promise<ConversationHistoryResponse> {
  return apiClient(`/chat/${conversationId}`, {
    method: "GET",
  });
}
