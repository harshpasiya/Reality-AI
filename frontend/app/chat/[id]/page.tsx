"use client";

import { useEffect, useState, use } from "react";
import { AiChat } from "@/components/ai-chat";
import GoogleMap from "@/components/map/GoogleMap";
import UserMenu from "@/components/UserMenu";
import {
  getConversationHistory,
  sendChatMessage,
  HistoricalMessage,
  Listing,
} from "@/lib/api/chat";

interface ChatPageProps {
  params: Promise<{ id: string }>;
}

function getLatestUniqueListings<T extends { id: number }>(items: T[]): T[] {
  const latestById = new Map<number, T>();

  for (const item of items) {
    latestById.set(item.id, item);
  }

  return [...latestById.values()];
}

export default function ChatPage({ params }: ChatPageProps) {
  const { id: conversationId } = use(params);

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [messages, setMessages] = useState<HistoricalMessage[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [hoveredListingId, setHoveredListingId] = useState<number | null>(null);
  const [hoveredCardKey, setHoveredCardKey] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSendingMessage, setIsSendingMessage] = useState(false);

  useEffect(() => {
    async function fetchHistory() {
      if (!conversationId) return;

      try {
        setIsLoadingHistory(true);
        const data = await getConversationHistory(conversationId);

        setMessages(data.messages || []);

        const allListings = (data.messages || []).flatMap(
          (msg) => msg.listings || [],
        );
        const latestListings = getLatestUniqueListings(allListings);
        console.log("Fetched listings from history:", latestListings);
        setListings(latestListings);
      } catch (error) {
        console.error("Failed to load conversation history:", error);
      } finally {
        setIsLoadingHistory(false);
      }
    }

    fetchHistory();
  }, [conversationId]);

  async function handleSendMessage(text: string) {
    const trimmedMessage = text.trim();
    if (!trimmedMessage || isSendingMessage) return;

    const optimisticUserMsg: HistoricalMessage = {
      id: `temp-${Date.now()}`,
      sender: "user",
      message: trimmedMessage,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);
    setIsSendingMessage(true);

    try {
      const response = await sendChatMessage({
        conversation_id: conversationId,
        message: trimmedMessage,
        polygon: null,
      });

      const assistantMsg: HistoricalMessage = {
        id: `msg-${Date.now()}`,
        sender: "assistant",
        message: response.reply,
        created_at: new Date().toISOString(),
        listings: response.listings,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (response.listings?.length) {
        setListings((prev) =>
          getLatestUniqueListings([...prev, ...response.listings]),
        );
      }
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsSendingMessage(false);
    }
  }

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden">
      <div className="fixed top-4 right-4 z-50">
        <UserMenu />
      </div>

      <div
        className={`absolute inset-x-0 top-0 w-full transition-all duration-500 ease-in-out ${
          isCollapsed ? "h-full" : "h-1/2"
        } lg:inset-0 lg:h-full`}
      >
        <GoogleMap
          listings={listings}
          hoveredListingId={hoveredListingId}
          onHoverListing={setHoveredListingId}
        />
      </div>

      <AiChat
        messages={messages}
        hoveredListingId={hoveredListingId}
        hoveredCardKey={hoveredCardKey}
        onHoverListing={setHoveredListingId}
        onHoverCard={setHoveredCardKey}
        isLoading={isLoadingHistory}
        isSending={isSendingMessage}
        onSendMessage={handleSendMessage}
        isCollapsed={isCollapsed}
        onToggle={() => {
          setIsCollapsed(!isCollapsed);
        }}
      />
    </main>
  );
}
