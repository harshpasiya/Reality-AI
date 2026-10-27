"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Eye, Inbox, Loader2, Mail, Plus, RefreshCw } from "lucide-react";
import {
  getBrokerAnalytics,
  getBrokerLeads,
  getBrokerListings,
  LEAD_STATUS_LABELS,
  updateLeadStatus,
  type BrokerAnalyticsResponse,
  type BrokerLeadItem,
  type BrokerListingItem,
  type LeadStatus,
} from "@/lib/api/broker";
import { errorMessage } from "@/lib/api/client";
import {
  formatPriceShort,
  STATUS_LABELS,
  updateListingStatus,
  type ListingStatus,
} from "@/lib/api/listings";
import { useAuthStore } from "@/stores/authStore";
import AppHeader from "@/components/AppHeader";

type Tab = "listings" | "leads";

const LISTING_STATUSES = Object.keys(STATUS_LABELS) as ListingStatus[];
const LEAD_STATUSES = Object.keys(LEAD_STATUS_LABELS) as LeadStatus[];

const selectClass =
  "rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 outline-none focus:border-accent disabled:opacity-50";

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-1 text-sm text-slate-500">{hint}</p>
    </div>
  );
}

export default function BrokerDashboardPage() {
  const user = useAuthStore((state) => state.user);
  const [analytics, setAnalytics] = useState<BrokerAnalyticsResponse | null>(
    null,
  );
  const [listings, setListings] = useState<BrokerListingItem[]>([]);
  const [leads, setLeads] = useState<BrokerLeadItem[]>([]);
  const [tab, setTab] = useState<Tab>("listings");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Bumped by "Retry" to load everything again.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([
      getBrokerAnalytics(user.id),
      getBrokerListings(user.id),
      getBrokerLeads(user.id),
    ])
      .then(([a, l, d]) => {
        if (cancelled) return;
        setAnalytics(a);
        setListings(l);
        setLeads(d);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(errorMessage(err, "Failed to load your dashboard."));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  async function changeListingStatus(id: number, status: ListingStatus) {
    setBusyId(`l-${id}`);
    setError(null);
    try {
      const updated = await updateListingStatus(id, status);
      setListings((prev) =>
        prev.map((l) => (l.id === id ? { ...l, status: updated.status } : l)),
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn't change the status."));
    } finally {
      setBusyId(null);
    }
  }

  async function changeLeadStatus(id: number, status: LeadStatus) {
    setBusyId(`d-${id}`);
    setError(null);
    try {
      const updated = await updateLeadStatus(id, status);
      setLeads((prev) =>
        prev.map((l) => (l.id === id ? { ...l, status: updated.status } : l)),
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn't update the enquiry."));
    } finally {
      setBusyId(null);
    }
  }

  const newLeads = leads.filter((l) => l.status === "new").length;
  const dash = loading ? "—" : undefined;

  return (
    <main className="min-h-screen bg-slate-50/50 text-slate-900">
      <AppHeader homeHref="/broker/dashboard" />
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        <section className="flex flex-col gap-6 rounded-2xl border border-slate-200 bg-white p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-500">
              Broker dashboard
            </p>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-4xl">
              Welcome back, {user?.name}
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600 sm:text-base">
              Listings you add are searchable by customers through the Reality
              AI chat within a minute.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href={user ? `/brokers/${user.id}` : "#"}
              className="inline-flex h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium transition hover:bg-slate-50"
            >
              Public profile
            </Link>
            <Link
              href="/broker/listings/create"
              className="bg-accent hover:bg-accent-hover inline-flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg px-5 text-sm font-medium text-white transition"
            >
              <Plus className="h-4 w-4" />
              Add listing
            </Link>
          </div>
        </section>

        {error && (
          <div
            role="alert"
            className="mt-6 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                setReloadKey((k) => k + 1);
              }}
              className="inline-flex items-center gap-1 font-medium underline"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        )}

        <section className="mt-8 grid gap-4 sm:grid-cols-3">
          <StatCard
            label="Listings"
            value={dash ?? analytics?.total_listings ?? 0}
            hint="All statuses"
          />
          <StatCard
            label="Views"
            value={dash ?? analytics?.total_views ?? 0}
            hint="Detail opens and chat appearances"
          />
          <StatCard
            label="Enquiries"
            value={dash ?? analytics?.total_leads ?? 0}
            hint={newLeads ? `${newLeads} new` : "Customers who contacted you"}
          />
        </section>

        <div
          className="mt-8 flex gap-1 border-b border-slate-200"
          role="tablist"
        >
          {(
            [
              ["listings", `My listings (${listings.length})`],
              ["leads", `Enquiries (${leads.length})`],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                tab === key
                  ? "border-accent text-accent"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16 text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : tab === "listings" ? (
          listings.length === 0 ? (
            <section className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
              <h2 className="text-lg font-semibold">
                Start by adding a listing
              </h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
                Add your first property to make it discoverable through Reality
                AI.
              </p>
              <Link
                href="/broker/listings/create"
                className="mt-5 inline-flex h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium transition hover:bg-slate-50"
              >
                Add your first listing
              </Link>
            </section>
          ) : (
            <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="px-4 py-3 font-medium">Property</th>
                    <th className="px-4 py-3 font-medium">Price</th>
                    <th className="px-4 py-3 font-medium">Views</th>
                    <th className="px-4 py-3 font-medium">Enquiries</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {listings.map((l) => (
                    <tr key={l.id} className="hover:bg-slate-50/60">
                      <td className="max-w-xs px-4 py-3">
                        <Link
                          href={`/listings/${l.id}`}
                          className="hover:text-accent line-clamp-1 font-medium text-slate-800"
                        >
                          {l.title}
                        </Link>
                        <span className="text-xs text-slate-500">
                          {l.images.length
                            ? `${l.images.length} photo${l.images.length === 1 ? "" : "s"}`
                            : "No photos"}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold">
                        {formatPriceShort(l.price)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-slate-600">
                          <Eye className="h-3.5 w-3.5" />
                          {l.view_count}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-slate-600">
                          <Inbox className="h-3.5 w-3.5" />
                          {l.lead_count}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <label className="sr-only" htmlFor={`status-${l.id}`}>
                          Status of {l.title}
                        </label>
                        <select
                          id={`status-${l.id}`}
                          value={l.status}
                          disabled={busyId === `l-${l.id}`}
                          onChange={(e) =>
                            changeListingStatus(
                              l.id,
                              e.target.value as ListingStatus,
                            )
                          }
                          className={selectClass}
                        >
                          {LISTING_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {STATUS_LABELS[s]}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : leads.length === 0 ? (
          <p className="mt-10 text-center text-sm text-slate-500">
            No enquiries yet. They appear here when a customer taps
            &ldquo;Contact broker&rdquo; on one of your listings.
          </p>
        ) : (
          <ul className="mt-6 space-y-3">
            {leads.map((lead) => (
              <li
                key={lead.id}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900">
                      {lead.customer_name}
                      {lead.status === "new" && (
                        <span className="bg-accent ml-2 rounded px-1.5 py-0.5 text-[10px] font-semibold text-white uppercase">
                          New
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">
                      about{" "}
                      <Link
                        href={`/listings/${lead.listing_id}`}
                        className="hover:text-accent font-medium"
                      >
                        {lead.listing_title}
                      </Link>{" "}
                      ·{" "}
                      {new Date(lead.created_at).toLocaleString("en-IN", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                    {lead.message && (
                      <p className="mt-2 text-sm whitespace-pre-line text-slate-700">
                        {lead.message}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <a
                      href={`mailto:${lead.customer_email}?subject=${encodeURIComponent(`Your enquiry: ${lead.listing_title}`)}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <Mail className="h-3.5 w-3.5" />
                      Reply
                    </a>
                    <label className="sr-only" htmlFor={`lead-${lead.id}`}>
                      Follow-up status
                    </label>
                    <select
                      id={`lead-${lead.id}`}
                      value={lead.status}
                      disabled={busyId === `d-${lead.id}`}
                      onChange={(e) =>
                        changeLeadStatus(lead.id, e.target.value as LeadStatus)
                      }
                      className={selectClass}
                    >
                      {LEAD_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {LEAD_STATUS_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
