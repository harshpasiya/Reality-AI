import { apiClient, mediaUrl } from "./client";

export type BackendPropertyType = "flat" | "house_land";
export type ListingStatus = "available" | "under_offer" | "sold" | "withdrawn";

export interface Rooms {
  bedrooms?: number | null;
  bathrooms?: number | null;
  balconies?: number | null;
  hall?: number | null;
  kitchen?: number | null;
  garden?: number | null;
}

export interface ListingImage {
  url: string;
  order: number;
}

/** One nearby place cached by the AI amenities service (Google Places). */
export interface NearbyPlace {
  name: string;
  distance_m: number;
  rating: number | null;
  user_ratings_total?: number;
}

/** Category -> nearby places, e.g. {"schools": [...], "transit": [...]}. */
export type Amenities = Record<string, NearbyPlace[]>;

/** A listing exactly as the backend returns it (ListingResponse). */
export interface Listing {
  id: number;
  broker_id: number;
  title: string;
  description: string | null;
  price: number;
  property_type: BackendPropertyType;
  carpet_area: number | null;
  built_up_area: number | null;
  plot_area: number | null;
  floor_number: number | null;
  rooms: Rooms | null;
  lat: number | null;
  lng: number | null;
  amenities: Amenities | null;
  status: ListingStatus;
  images: ListingImage[];
  created_at: string;
  updated_at?: string | null;
}

/** @deprecated Use Listing. Kept so older imports keep compiling. */
export type ListingResponse = Listing;

export interface CreateListingRequest {
  title: string;
  description: string | null;
  price: number;
  property_type: BackendPropertyType;
  carpet_area: number | null;
  built_up_area: number | null;
  plot_area: number | null;
  floor_number: number | null;
  rooms: Rooms | null;
  lat: number;
  lng: number;
}

export interface Locality {
  name: string;
  lat: number;
  lng: number;
  radius_m: number;
}

interface ListingExtractionResponse {
  formData?: Record<string, string>;
  error?: string;
}

export const STATUS_LABELS: Record<ListingStatus, string> = {
  available: "Available",
  under_offer: "Under offer",
  sold: "Sold",
  withdrawn: "Withdrawn",
};

/** Photo URLs in display order, ready for <img src>. */
export function listingImageUrls(listing: Pick<Listing, "images">): string[] {
  return [...(listing.images ?? [])]
    .sort((a, b) => a.order - b.order)
    .map((image) => mediaUrl(image.url))
    .filter((url): url is string => Boolean(url));
}

export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Indian short form: ₹45 L, ₹1.2 Cr. */
export function formatPriceShort(amount: number): string {
  if (amount >= 1e7) return `₹${+(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${+(amount / 1e5).toFixed(1)} L`;
  return formatINR(amount);
}

export function formatPropertyType(type: BackendPropertyType): string {
  return type === "flat" ? "Flat" : "House / Plot";
}

export function extractListingDetails(
  description: string,
): Promise<ListingExtractionResponse> {
  return apiClient<ListingExtractionResponse>("/api/broker/listings/extract", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function createListing(data: CreateListingRequest): Promise<Listing> {
  return apiClient("/listings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Upload one photo (JPEG or PNG, at most 5 MB) to an existing listing. */
export function uploadListingImage(
  listingId: number,
  file: File,
): Promise<Listing> {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient<Listing>(`/listings/${listingId}/images`, {
    method: "POST",
    body: formData,
  });
}

export function getListing(listingId: number): Promise<Listing> {
  return apiClient(`/listings/${listingId}`, {
    method: "GET",
  });
}

export function updateListingStatus(
  listingId: number,
  status: ListingStatus,
): Promise<Listing> {
  return apiClient(`/listings/${listingId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getLocalities(): Promise<Locality[]> {
  return apiClient("/localities", { method: "GET" });
}
