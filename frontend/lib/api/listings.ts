import { apiClient, getResponseErrorMessage } from "./client";

export type BackendPropertyType = "flat" | "house_land";

export interface CreateListingRequest {
  title: string;
  description: string | null;
  price: number;
  property_type: BackendPropertyType;
  carpet_area: number | null;
  built_up_area: number | null;
  plot_area: number | null;
  floor_number: number | null;
  rooms: Record<string, unknown> | null;
  lat: number;
  lng: number;
  images: string[];
  video_tour_url: string | null;
}

export interface ListingResponse {
  id: number;
  title: string;
  description: string | null;
  price: number;
  property_type: BackendPropertyType;
  carpet_area: number | null;
  built_up_area: number | null;
  plot_area: number | null;
  floor_number: number | null;
  rooms: Record<string, unknown> | null;
  lat: number;
  lng: number;
  broker_id: number;
  amenities: Record<string, unknown> | null;
  created_at: string;
  images?: string[] | null;
  video_tour_url?: string | null;
}

interface ListingImageUploadResponse {
  url: string;
}

interface SignedVideoUploadResponse {
  upload_url: string;
  public_url: string;
}

interface ListingExtractionResponse {
  formData?: Record<string, string>;
  error?: string;
}

export function extractListingDetails(
  description: string,
): Promise<ListingExtractionResponse> {
  return apiClient<ListingExtractionResponse>("/api/broker/listings/extract", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function createListing(
  data: CreateListingRequest,
): Promise<ListingResponse> {
  return apiClient("/listings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function uploadListingImage(
  file: File,
): Promise<ListingImageUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("media_type", "image");

  return apiClient<ListingImageUploadResponse>("/listings/upload-media", {
    method: "POST",
    body: formData,
  });
}

export async function uploadListingVideo(file: File): Promise<string> {
  const contentType =
    file.type ||
    (file.name.toLowerCase().endsWith(".webm") ? "video/webm" : "video/mp4");
  const { upload_url, public_url } = await apiClient<SignedVideoUploadResponse>(
    "/listings/signed-upload-url",
    {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_type: contentType,
        media_type: "video",
      }),
    },
  );

  const response = await fetch(upload_url, {
    method: "PUT",
    headers: {
      "Content-Type": contentType,
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(
      `Video upload failed: ${await getResponseErrorMessage(response)}`,
    );
  }

  return public_url;
}

export function getListing(listingId: number): Promise<ListingResponse> {
  return apiClient(`/listings/${listingId}`, {
    method: "GET",
  });
}
