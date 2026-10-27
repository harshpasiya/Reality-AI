import { apiClient } from "./client";

export interface ListingAnalyticsItem {
  listing_id: number;
  title: string;
  lead_count: number;
}

export interface BrokerAnalyticsResponse {
  total_listings: number;
  total_leads: number;
  listings_breakdown: ListingAnalyticsItem[];
}

export function getBrokerAnalytics(
  brokerId: number,
): Promise<BrokerAnalyticsResponse> {
  return apiClient(`/brokers/${brokerId}/analytics`, {
    method: "GET",
  });
}
