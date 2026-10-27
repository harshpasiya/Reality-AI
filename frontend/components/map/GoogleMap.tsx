"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import {
  APIProvider,
  AdvancedMarker,
  Map,
  useMap,
} from "@vis.gl/react-google-maps";
import { Listing } from "@/lib/api/chat";
import { cn } from "@/lib/utils";

const DEFAULT_CENTER = {
  lat: 21.1702,
  lng: 72.8311,
};

const DEFAULT_ZOOM = 13;

interface GoogleMapProps {
  listings?: Listing[];
  hoveredListingId?: number | null;
  onHoverListing?: (listingId: number | null) => void;
}

function getCoordinates(property: any) {
  const lat = property.lat ?? property.location?.lat;
  const lng = property.lng ?? property.location?.lng;

  if (typeof lat === "number" && typeof lng === "number") {
    return { lat, lng };
  }
  return null;
}

function getAverageCenter(listings: Listing[]) {
  const validCoords = listings
    .map(getCoordinates)
    .filter(
      (coords): coords is { lat: number; lng: number } => coords !== null,
    );

  if (validCoords.length === 0) return DEFAULT_CENTER;

  const sum = validCoords.reduce(
    (acc, curr) => ({
      lat: acc.lat + curr.lat,
      lng: acc.lng + curr.lng,
    }),
    { lat: 0, lng: 0 },
  );

  return {
    lat: sum.lat / validCoords.length,
    lng: sum.lng / validCoords.length,
  };
}

function MapPanControl({ center }: { center: { lat: number; lng: number } }) {
  const map = useMap();

  useEffect(() => {
    if (map) {
      map.panTo(center);
    }
  }, [map, center]);

  return null;
}

export default function GoogleMap({
  listings = [],
  hoveredListingId = null,
  onHoverListing,
}: GoogleMapProps) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const mapId = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID;

  const center = useMemo(() => getAverageCenter(listings), [listings]);

  if (!apiKey || !mapId) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        Google Maps API configuration missing.
      </div>
    );
  }

  return (
    <APIProvider apiKey={apiKey}>
      <Map
        mapId={mapId}
        defaultCenter={center}
        defaultZoom={DEFAULT_ZOOM}
        gestureHandling="greedy"
        disableDefaultUI
        className="h-full w-full"
      >
        <MapPanControl center={center} />

        {listings.map((property, index) => {
          const coords = getCoordinates(property);
          if (!coords) return null;

          const isHovered = hoveredListingId === property.id;

          return (
            <AdvancedMarker
              key={`${property.id}-${index}`}
              position={coords}
              title={property.title}
              className="pointer-events-auto"
              onMouseEnter={() => onHoverListing?.(property.id)}
              onMouseLeave={() => onHoverListing?.(null)}
              style={{ pointerEvents: "auto", cursor: "pointer" }}
            >
              <Link
                href={`/listings/${property.id}`}
                className="block rounded-full focus:outline-none"
                aria-label={`View ${property.title}`}
              >
                <div
                  className={cn(
                    "relative flex size-11 items-center justify-center transition-all duration-200",
                    isHovered && "scale-110",
                  )}
                >
                  <div
                    className={cn(
                      "bg-accent flex size-11 items-center justify-center rounded-full border-4 border-white text-white shadow-lg transition-all duration-200",
                      isHovered &&
                        "bg-accent-border shadow-[0_0_0_8px_rgba(111,99,200,0.15)]",
                    )}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="size-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M3 11.5 12 4l9 7.5" />
                      <path d="M5.5 10.5V20h13v-9.5" />
                      <path d="M9.5 20v-5h5v5" />
                    </svg>
                  </div>
                  <div
                    className={cn(
                      "bg-accent absolute -bottom-1 h-3 w-3 rotate-45 border-r-4 border-b-4 border-white transition-colors duration-200",
                      isHovered && "bg-accent-border",
                    )}
                  />
                </div>
              </Link>
            </AdvancedMarker>
          );
        })}
      </Map>
    </APIProvider>
  );
}
