import { apiClient } from "./client";
import type { Listing, ListingStatus } from "./listings";

export interface ListingAnalyticsItem {
  listing_id: number;
  title: string;
  status: ListingStatus;
  view_count: number;
  lead_count: number;
}

export interface BrokerAnalyticsResponse {
  total_listings: number;
  total_views: number;
  total_leads: number;
  listings_breakdown: ListingAnalyticsItem[];
}

/** A row in the broker's own listings table. */
export interface BrokerListingItem extends Listing {
  view_count: number;
  lead_count: number;
}

export type LeadStatus =
  "new" | "contacted" | "visit_scheduled" | "closed" | "lost";

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  visit_scheduled: "Visit scheduled",
  closed: "Closed",
  lost: "Lost",
};

export interface Lead {
  id: number;
  listing_id: number;
  customer_id: number;
  message: string | null;
  status: LeadStatus;
  conversation_id: number | null;
  created_at: string;
  updated_at: string;
}

/** A lead in the broker's inbox. */
export interface BrokerLeadItem extends Lead {
  listing_title: string;
  customer_name: string;
  customer_email: string;
}

/** Returned to the customer after "Contact broker". */
export interface LeadCreateResponse extends Lead {
  broker: { name: string; phone: string | null };
}

export interface BrokerPublicProfile {
  id: number;
  name: string;
  member_since: string;
  active_listings: number;
  listings: Listing[];
}

export function getBrokerAnalytics(
  brokerId: number,
): Promise<BrokerAnalyticsResponse> {
  return apiClient(`/brokers/${brokerId}/analytics`, {
    method: "GET",
  });
}

export function getBrokerListings(
  brokerId: number,
): Promise<BrokerListingItem[]> {
  return apiClient(`/brokers/${brokerId}/listings?limit=100`, {
    method: "GET",
  });
}

export function getBrokerLeads(brokerId: number): Promise<BrokerLeadItem[]> {
  return apiClient(`/brokers/${brokerId}/leads?limit=100`, { method: "GET" });
}

export function updateLeadStatus(
  leadId: number,
  status: LeadStatus,
): Promise<Lead> {
  return apiClient(`/leads/${leadId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getBrokerPublicProfile(
  brokerId: number,
): Promise<BrokerPublicProfile> {
  return apiClient(`/brokers/${brokerId}/public`, { method: "GET" });
}

/** The customer's earlier enquiry on a listing (404 ApiError if none). */
export function getMyLead(listingId: number): Promise<LeadCreateResponse> {
  return apiClient(`/listings/${listingId}/leads/mine`, { method: "GET" });
}

/** "Contact broker": records an enquiry and reveals the broker's phone. */
export function contactBroker(
  listingId: number,
  message: string | null,
  conversationId: number | null = null,
): Promise<LeadCreateResponse> {
  return apiClient(`/listings/${listingId}/leads`, {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}
