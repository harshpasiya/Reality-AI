"use client";

import { cn } from "@/lib/utils";
import ChatHeader from "./ChatHeader";
import ChatInput from "./ChatInput";
import ChatMessages from "./ChatArea";
import { HistoricalMessage } from "@/lib/api/chat";

type AiChatProps = {
  isCollapsed: boolean;
  onToggle: () => void;
  messages: HistoricalMessage[];
  hoveredListingId?: number | null;
  hoveredCardKey?: string | null;
  onHoverListing?: (listingId: number | null) => void;
  onHoverCard?: (cardKey: string | null) => void;
  isLoading?: boolean;
  isSending?: boolean;
  onSendMessage: (text: string) => void;
};

export default function AiChat({
  isCollapsed,
  onToggle,
  messages,
  hoveredListingId = null,
  hoveredCardKey = null,
  onHoverListing,
  onHoverCard,
  isLoading = false,
  isSending = false,
  onSendMessage,
}: AiChatProps) {
  return (
    <aside
      data-collapsed={isCollapsed}
      className={cn(
        // base + glass
        "glass absolute inset-x-0 bottom-0 z-20 flex flex-col overflow-hidden",

        // animation
        "transition-transform duration-500 ease-in-out [--chat-header-h:4rem]",

        // mobile sheet
        "shadow-chat-sheet h-1/2 rounded-t-3xl",

        // mobile collapse
        "data-[collapsed=true]:translate-y-[calc(100%-var(--chat-header-h))]",

        // desktop layout
        "lg:shadow-chat-panel lg:inset-y-4 lg:right-auto lg:left-4 lg:h-auto lg:w-[380px] lg:rounded-3xl",

        // desktop collapse
        "lg:data-[collapsed=true]:translate-x-[calc(-100%+2.75rem)] lg:data-[collapsed=true]:translate-y-0",

        // wide desktop
        "xl:w-[400px]",
      )}
    >
      <ChatHeader isCollapsed={isCollapsed} onToggle={onToggle} />

      <div
        className={cn(
          "flex flex-1 flex-col overflow-hidden transition-opacity duration-300",
          isCollapsed ? "pointer-events-none opacity-0" : "opacity-100",
        )}
      >
        <div className="min-h-0 flex-1 overflow-hidden">
          {isLoading ? (
            <div className="text-text-muted flex h-full items-center justify-center text-sm">
              Loading chat history...
            </div>
          ) : (
            <ChatMessages
              messages={messages}
              hoveredListingId={hoveredListingId}
              hoveredCardKey={hoveredCardKey}
              onHoverListing={onHoverListing}
              onHoverCard={onHoverCard}
            />
          )}
        </div>

        <ChatInput onSend={onSendMessage} disabled={isSending} />
      </div>
    </aside>
  );
}
