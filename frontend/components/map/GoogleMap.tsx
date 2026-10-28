"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import {
  APIProvider,
  AdvancedMarker,
  Map,
  useMap,
} from "@vis.gl/react-google-maps";
import { MapPinOff } from "lucide-react";
import type { Listing } from "@/lib/api/listings";
import { formatPriceShort } from "@/lib/api/listings";
import { cn } from "@/lib/utils";

// Surat city centre.
const DEFAULT_CENTER = {
  lat: 21.1702,
  lng: 72.8311,
};

const DEFAULT_ZOOM = 13;

// Google's documented demo map ID: Advanced Markers work with only an API key.
// Set NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID to use your own styled map instead.
const FALLBACK_MAP_ID = "DEMO_MAP_ID";

interface GoogleMapProps {
  listings?: Listing[];
  hoveredListingId?: number | null;
  onHoverListing?: (listingId: number | null) => void;
}

type Coords = { lat: number; lng: number };

function getCoordinates(listing: Listing): Coords | null {
  const { lat, lng } = listing;
  if (typeof lat === "number" && typeof lng === "number") {
    return { lat, lng };
  }
  return null;
}

/** Fit the map to the listings whenever the result set changes. */
function FitToListings({ points }: { points: Coords[] }) {
  const map = useMap();

  useEffect(() => {
    if (!map || points.length === 0) return;
    if (points.length === 1) {
      map.panTo(points[0]);
      map.setZoom(15);
      return;
    }
    const lats = points.map((p) => p.lat);
    const lngs = points.map((p) => p.lng);
    map.fitBounds(
      {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lngs),
        west: Math.min(...lngs),
      },
      80,
    );
  }, [map, points]);

  return null;
}

export default function GoogleMap({
  listings = [],
  hoveredListingId = null,
  onHoverListing,
}: GoogleMapProps) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const mapId = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID || FALLBACK_MAP_ID;

  const points = useMemo(
    () =>
      listings
        .map(getCoordinates)
        .filter((coords): coords is Coords => coords !== null),
    [listings],
  );

  if (!apiKey) {
    return (
      <div className="bg-surface-soft text-text-secondary flex h-full w-full flex-col items-center justify-center gap-2 px-6 text-center text-sm">
        <MapPinOff className="h-6 w-6" aria-hidden="true" />
        <p>The map is not configured.</p>
        <p className="text-text-muted text-xs">
          Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY in frontend/.env.local. Results
          still appear in the chat.
        </p>
      </div>
    );
  }

  return (
    <APIProvider apiKey={apiKey}>
      <Map
        mapId={mapId}
        defaultCenter={DEFAULT_CENTER}
        defaultZoom={DEFAULT_ZOOM}
        gestureHandling="greedy"
        disableDefaultUI
        className="h-full w-full"
      >
        <FitToListings points={points} />

        {listings.map((listing) => {
          const coords = getCoordinates(listing);
          if (!coords) return null;

          const isHovered = hoveredListingId === listing.id;

          return (
            <AdvancedMarker
              key={listing.id}
              position={coords}
              title={listing.title}
              zIndex={isHovered ? 10 : 1}
              onMouseEnter={() => onHoverListing?.(listing.id)}
              onMouseLeave={() => onHoverListing?.(null)}
              style={{ pointerEvents: "auto", cursor: "pointer" }}
            >
              <Link
                href={`/listings/${listing.id}`}
                aria-label={`${listing.title}, ${formatPriceShort(listing.price)}`}
                className={cn(
                  "bg-ink relative block rounded-full border-2 border-white px-2.5 py-1 text-xs font-bold whitespace-nowrap text-white shadow-lg transition-transform duration-200",
                  isHovered && "bg-accent scale-110",
                )}
              >
                {formatPriceShort(listing.price)}
                <span
                  aria-hidden="true"
                  className={cn(
                    "bg-ink absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-r-2 border-b-2 border-white",
                    isHovered && "bg-accent",
                  )}
                />
              </Link>
            </AdvancedMarker>
          );
        })}
      </Map>
    </APIProvider>
  );
}
