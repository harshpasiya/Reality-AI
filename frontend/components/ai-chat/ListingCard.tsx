"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { Listing } from "@/lib/api/chat";
import { Bed, Bath, Maximize2, MapPin } from "lucide-react";
import PropertyImage from "@/components/PropertyImage";

interface ListingCardProps {
  listing: Listing;
  onSelect?: (listing: Listing) => void;
  cardKey?: string;
  isHovered?: boolean;
  onHoverChange?: (isHovered: boolean) => void;
}

export default function ListingCard({
  listing,
  onSelect,
  cardKey,
  isHovered = false,
  onHoverChange,
}: ListingCardProps) {
  const formattedPrice = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(listing.price);
  const imageSrc = listing.images?.find((image) => image.trim())?.trim();

  return (
    <Link
      href={`/listings/${listing.id}`}
      data-listing-id={listing.id}
      data-listing-key={cardKey ?? listing.id}
      onClick={() => onSelect?.(listing)}
      onMouseEnter={() => onHoverChange?.(true)}
      onMouseLeave={() => onHoverChange?.(false)}
      onFocus={() => onHoverChange?.(true)}
      onBlur={() => onHoverChange?.(false)}
      className={cn(
        "group block flex cursor-pointer flex-col gap-2 rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-xs transition-all duration-200 hover:border-slate-300 hover:shadow-md",
        isHovered &&
          "border-accent-border bg-accent-soft ring-accent/20 shadow-[0_10px_25px_rgba(111,99,200,0.12)] ring-2",
      )}
    >
      <PropertyImage
        src={imageSrc}
        alt={`${listing.title} property photo`}
        className="h-36 w-full rounded-xl"
        sizes="(max-width: 640px) 100vw, 400px"
      />

      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="group-hover:text-accent line-clamp-1 text-sm leading-snug font-semibold text-slate-800 transition-colors">
            {listing.title}
          </h4>
          <p className="mt-0.5 line-clamp-1 flex items-center gap-1 text-xs text-slate-500">
            <MapPin className="h-3 w-3 shrink-0 text-slate-400" />
            {listing.property_type.toUpperCase()} • Floor{" "}
            {listing.floor_number ?? "N/A"}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-lg bg-slate-100 px-2.5 py-1 text-sm font-bold text-slate-900 transition-colors",
            isHovered && "bg-accent text-white",
          )}
        >
          {formattedPrice}
        </span>
      </div>

      <p className="line-clamp-2 text-xs leading-relaxed text-slate-600">
        {listing.description}
      </p>

      <div className="flex items-center gap-3 border-t border-slate-100 pt-1 text-xs text-slate-500">
        {listing.rooms?.bedrooms && (
          <div className="flex items-center gap-1">
            <Bed className="h-3.5 w-3.5 text-slate-400" />
            <span>{listing.rooms.bedrooms} Bed</span>
          </div>
        )}
        {listing.rooms?.bathrooms && (
          <div className="flex items-center gap-1">
            <Bath className="h-3.5 w-3.5 text-slate-400" />
            <span>{listing.rooms.bathrooms} Bath</span>
          </div>
        )}
        {listing.carpet_area && (
          <div className="flex items-center gap-1">
            <Maximize2 className="h-3.5 w-3.5 text-slate-400" />
            <span>{listing.carpet_area} sq ft</span>
          </div>
        )}
      </div>
    </Link>
  );
}
