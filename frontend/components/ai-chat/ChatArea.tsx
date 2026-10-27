"use client";

import { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import { HistoricalMessage } from "@/lib/api/chat";

type ChatMessagesProps = {
  messages: HistoricalMessage[];
  isSending?: boolean;
  onRetry?: (text: string) => void;
  hoveredListingId?: number | null;
  hoveredCardKey?: string | null;
  onHoverListing?: (listingId: number | null) => void;
  onHoverCard?: (cardKey: string | null) => void;
};

export default function ChatArea({
  messages,
  isSending = false,
  onRetry,
  hoveredListingId = null,
  hoveredCardKey = null,
  onHoverListing,
  onHoverCard,
}: ChatMessagesProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

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
          const formattedTime = msg.timestamp
            ? new Date(msg.timestamp).toLocaleTimeString([], {
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
              failed={msg.failed}
              onRetry={
                msg.failed && !isSending
                  ? () => onRetry?.(msg.message)
                  : undefined
              }
              hoveredListingId={hoveredListingId}
              hoveredCardKey={hoveredCardKey}
              onHoverListing={onHoverListing}
              onHoverCard={onHoverCard}
            />
          );
        })}
        {messages.length === 0 && !isSending && (
          <p className="text-text-muted py-10 text-center text-sm">
            Ask for a property, e.g. &ldquo;2 BHK in Vesu under 80 lakh&rdquo;.
          </p>
        )}
        {isSending && (
          <div
            className="flex items-center gap-2 text-sm text-slate-500"
            aria-live="polite"
          >
            <span className="flex gap-1" aria-hidden="true">
              <span className="size-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
              <span className="size-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
              <span className="size-2 animate-bounce rounded-full bg-slate-400" />
            </span>
            Searching listings…
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
