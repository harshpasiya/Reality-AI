"use client";

import { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import { HistoricalMessage } from "@/lib/api/chat";

type ChatMessagesProps = {
  messages: HistoricalMessage[];
  hoveredListingId?: number | null;
  hoveredCardKey?: string | null;
  onHoverListing?: (listingId: number | null) => void;
  onHoverCard?: (cardKey: string | null) => void;
};

export default function ChatArea({
  messages,
  hoveredListingId = null,
  hoveredCardKey = null,
  onHoverListing,
  onHoverCard,
}: ChatMessagesProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (hoveredListingId === null) {
      if (hoveredCardKey !== null) {
        onHoverCard?.(null);
      }
      return;
    }

    if (hoveredCardKey) {
      const card = document.querySelector(
        `[data-listing-key="${hoveredCardKey}"]`,
      ) as HTMLElement | null;

      if (!card || !scrollContainerRef.current) return;

      const cardRect = card.getBoundingClientRect();
      const containerRect = scrollContainerRef.current.getBoundingClientRect();
      const isVisible =
        cardRect.top >= containerRect.top &&
        cardRect.bottom <= containerRect.bottom;

      if (!isVisible) {
        card.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
          inline: "nearest",
        });
      }
      return;
    }

    const cards = Array.from(
      document.querySelectorAll(`[data-listing-id="${hoveredListingId}"]`),
    ) as HTMLElement[];
    const lastCard = cards[cards.length - 1] ?? null;

    if (!lastCard) return;

    const nextCardKey = lastCard.dataset.listingKey ?? null;
    if (nextCardKey) {
      onHoverCard?.(nextCardKey);
    }

    if (!scrollContainerRef.current) return;

    const cardRect = lastCard.getBoundingClientRect();
    const containerRect = scrollContainerRef.current.getBoundingClientRect();
    const isVisible =
      cardRect.top >= containerRect.top &&
      cardRect.bottom <= containerRect.bottom;

    if (!isVisible) {
      lastCard.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest",
      });
    }
  }, [hoveredCardKey, hoveredListingId, onHoverCard]);

  return (
    <div
      ref={scrollContainerRef}
      className="fade-bottom h-full scrollbar-thin scrollbar-thumb-gray-200 overflow-y-auto px-5 py-6"
    >
      <div className="space-y-5">
        {messages.map((msg, index) => {
          const formattedTime = msg.created_at
            ? new Date(msg.created_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "";

          return (
            <ChatMessage
              key={msg.id || `msg-${index}`}
              role={msg.sender}
              content={msg.message}
              time={formattedTime}
              listings={msg.listings}
              messageKey={msg.id || `msg-${index}`}
              hoveredListingId={hoveredListingId}
              hoveredCardKey={hoveredCardKey}
              onHoverListing={onHoverListing}
              onHoverCard={onHoverCard}
            />
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}
