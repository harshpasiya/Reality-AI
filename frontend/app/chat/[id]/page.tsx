"use client";

import { useCallback, useEffect, useMemo, useState, use } from "react";
import Link from "next/link";
import { AiChat } from "@/components/ai-chat";
import GoogleMap from "@/components/map/GoogleMap";
import UserMenu from "@/components/UserMenu";
import {
  getConversationHistory,
  sendChatMessage,
  type ChatListing,
  type HistoricalMessage,
} from "@/lib/api/chat";
import { errorMessage, isApiError } from "@/lib/api/client";

interface ChatPageProps {
  params: Promise<{ id: string }>;
}

/** Listings of the most recent assistant reply that had any: the map shows these. */
function latestResults(messages: HistoricalMessage[]): ChatListing[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.sender === "assistant" && msg.listings?.length) return msg.listings;
  }
  return [];
}

export default function ChatPage({ params }: ChatPageProps) {
  const { id } = use(params);
  const conversationId = Number(id);

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [messages, setMessages] = useState<HistoricalMessage[]>([]);
  const [hoveredListingId, setHoveredListingId] = useState<number | null>(null);
  const [hoveredCardKey, setHoveredCardKey] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const listings = useMemo(() => latestResults(messages), [messages]);

  useEffect(() => {
    async function fetchHistory() {
      if (!Number.isInteger(conversationId) || conversationId <= 0) {
        setLoadError("This conversation doesn't exist.");
        setIsLoadingHistory(false);
        return;
      }

      try {
        setIsLoadingHistory(true);
        const data = await getConversationHistory(conversationId);
        setMessages(
          (data.messages || []).map((msg, index) => ({
            ...msg,
            id: `h-${index}`,
          })),
        );
      } catch (error) {
        setLoadError(
          isApiError(error, 404)
            ? "This conversation doesn't exist or belongs to another account."
            : errorMessage(error, "Couldn't load this conversation."),
        );
      } finally {
        setIsLoadingHistory(false);
      }
    }

    fetchHistory();
  }, [conversationId]);

  const handleSendMessage = useCallback(
    async (text: string) => {
      const trimmedMessage = text.trim();
      if (!trimmedMessage || isSendingMessage) return;

      const userMsgId = `u-${Date.now()}`;
      setSendError(null);
      setMessages((prev) => [
        // Drop an earlier failed copy of the same text when retrying.
        ...prev.filter((m) => !(m.failed && m.message === trimmedMessage)),
        {
          id: userMsgId,
          sender: "user",
          message: trimmedMessage,
          timestamp: new Date().toISOString(),
        },
      ]);
      setIsSendingMessage(true);

      try {
        const response = await sendChatMessage({
          conversation_id: conversationId,
          message: trimmedMessage,
          polygon: null,
        });

        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            sender: "assistant",
            message: response.reply,
            timestamp: new Date().toISOString(),
            listings: response.listings,
          },
        ]);
      } catch (error) {
        setMessages((prev) =>
          prev.map((m) => (m.id === userMsgId ? { ...m, failed: true } : m)),
        );
        setSendError(
          errorMessage(error, "Your message couldn't be sent. Please retry."),
        );
      } finally {
        setIsSendingMessage(false);
      }
    },
    [conversationId, isSendingMessage],
  );

  if (loadError) {
    return (
      <main className="bg-surface-soft flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-text-primary text-lg font-semibold">{loadError}</p>
        <Link
          href="/"
          className="bg-accent hover:bg-accent-hover rounded-xl px-5 py-2.5 text-sm font-medium text-white"
        >
          Start a new search
        </Link>
      </main>
    );
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
        sendError={sendError}
        onSendMessage={handleSendMessage}
        isCollapsed={isCollapsed}
        onToggle={() => {
          setIsCollapsed(!isCollapsed);
        }}
      />
    </main>
  );
}
