"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ChatListing } from "@/lib/api/chat";
import {
  formatPriceShort,
  formatPropertyType,
  listingImageUrls,
  STATUS_LABELS,
} from "@/lib/api/listings";
import { Bed, Bath, Maximize2, Building2 } from "lucide-react";
import PropertyImage from "@/components/PropertyImage";

interface ListingCardProps {
  listing: ChatListing;
  onSelect?: (listing: ChatListing) => void;
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
  const imageSrc = listingImageUrls(listing)[0];
  const bedrooms = listing.rooms?.bedrooms ?? listing.bhk ?? null;
  const bathrooms = listing.rooms?.bathrooms ?? null;
  const area = listing.carpet_area ?? listing.plot_area ?? null;

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
          "border-accent-border bg-accent-soft ring-accent/20 shadow-[0_10px_25px_rgba(4,120,87,0.12)] ring-2",
      )}
    >
      <div className="relative">
        <PropertyImage
          src={imageSrc}
          alt={`${listing.title} property photo`}
          className="h-36 w-full rounded-xl"
          sizes="(max-width: 640px) 100vw, 400px"
        />
        {listing.status === "under_offer" && (
          <span className="absolute top-2 left-2 rounded-md bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white">
            {STATUS_LABELS.under_offer}
          </span>
        )}
      </div>

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="group-hover:text-accent line-clamp-1 text-sm leading-snug font-semibold text-slate-800 transition-colors">
            {listing.title}
          </h4>
          <p className="mt-0.5 line-clamp-1 flex items-center gap-1 text-xs text-slate-500">
            <Building2 className="h-3 w-3 shrink-0 text-slate-400" />
            {formatPropertyType(listing.property_type)}
            {listing.floor_number !== null &&
              ` • Floor ${listing.floor_number}`}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-lg bg-slate-100 px-2.5 py-1 text-sm font-bold text-slate-900 transition-colors",
            isHovered && "bg-accent text-white",
          )}
        >
          {formatPriceShort(listing.price)}
        </span>
      </div>

      {listing.description && (
        <p className="line-clamp-2 text-xs leading-relaxed text-slate-600">
          {listing.description}
        </p>
      )}

      {(bedrooms !== null || bathrooms !== null || area !== null) && (
        <div className="flex items-center gap-3 border-t border-slate-100 pt-1 text-xs text-slate-500">
          {bedrooms !== null && (
            <div className="flex items-center gap-1">
              <Bed className="h-3.5 w-3.5 text-slate-400" />
              <span>{bedrooms} BHK</span>
            </div>
          )}
          {bathrooms !== null && (
            <div className="flex items-center gap-1">
              <Bath className="h-3.5 w-3.5 text-slate-400" />
              <span>{bathrooms} Bath</span>
            </div>
          )}
          {area !== null && (
            <div className="flex items-center gap-1">
              <Maximize2 className="h-3.5 w-3.5 text-slate-400" />
              <span>{Math.round(area).toLocaleString("en-IN")} sq ft</span>
            </div>
          )}
        </div>
      )}
    </Link>
  );
}
