import { cn } from "@/lib/utils";
import { HistoricalMessage } from "@/lib/api/chat";
import ListingCard from "@/components/ai-chat/ListingCard";

const BUBBLE_STYLES = {
  assistant:
    "rounded-tl-md border border-slate-100 bg-[#F8FAFC] text-slate-800",
  user: "rounded-tr-md bg-[#1E1E24] text-white",
} as const;

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  time?: string;
  listings?: HistoricalMessage["listings"];
  messageKey?: string;
  hoveredListingId?: number | null;
  hoveredCardKey?: string | null;
  onHoverListing?: (listingId: number | null) => void;
  onHoverCard?: (cardKey: string | null) => void;
}

export default function ChatMessage({
  role,
  content,
  time,
  listings,
  messageKey,
  hoveredListingId = null,
  hoveredCardKey = null,
  onHoverListing,
  onHoverCard,
}: ChatMessageProps) {
  const isAssistant = role === "assistant";
  const hasListings = isAssistant && listings && listings.length > 0;

  return (
    <div
      className={cn("flex flex-col", isAssistant ? "items-start" : "items-end")}
    >
      <div className="max-w-[88%] space-y-2 sm:max-w-[80%]">
        <div
          className={cn(
            "rounded-[20px] px-4 py-3 text-[15px] leading-relaxed shadow-xs",
            BUBBLE_STYLES[role],
          )}
        >
          <p className="break-words">{content}</p>
        </div>

        {hasListings && (
          <div className="mt-2.5 space-y-2">
            {listings.map((listing, listingIndex) => {
              const cardKey = `${messageKey ?? "msg"}-${listing.id}-${listingIndex}`;

              return (
                <ListingCard
                  key={cardKey}
                  listing={listing}
                  cardKey={cardKey}
                  isHovered={hoveredCardKey === cardKey}
                  onHoverChange={(isHovered) => {
                    if (isHovered) {
                      onHoverCard?.(cardKey);
                      onHoverListing?.(listing.id);
                      return;
                    }

                    onHoverCard?.(null);
                    onHoverListing?.(null);
                  }}
                />
              );
            })}
          </div>
        )}

        <span
          className={cn(
            "mt-1 block px-1 text-xs text-slate-400",
            isAssistant ? "text-left" : "text-right",
          )}
        >
          {time}
        </span>
      </div>
    </div>
  );
}
