"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getBrokerAnalytics,
  type BrokerAnalyticsResponse,
} from "@/lib/api/broker";
import { useAuthStore } from "@/stores/authStore";
import AppHeader from "@/components/AppHeader";

export default function BrokerDashboardPage() {
  const user = useAuthStore((state) => state.user);
  const [analytics, setAnalytics] = useState<BrokerAnalyticsResponse | null>(
    null,
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAnalytics() {
      try {
        setLoading(true);
        setError(null);

        if (!user) return;

        const data = await getBrokerAnalytics(user.id);

        if (!cancelled) {
          setAnalytics(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load broker analytics.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAnalytics();

    return () => {
      cancelled = true;
    };
  }, [user]);

  const totalListings = analytics?.total_listings ?? 0;
  const totalLeads = analytics?.total_leads ?? 0;

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <AppHeader />

      <div className="mx-auto max-w-7xl px-6 py-10">
        <section className="flex flex-col gap-6 rounded-2xl border border-slate-200 bg-slate-50 p-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-500">
              Broker Dashboard
            </p>

            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Welcome back, {user?.name}
            </h1>

            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600 sm:text-base">
              Create and manage your property listings with Reality AI.
            </p>
          </div>

          <Link
            href="/broker/listings/create"
            className="bg-accent hover:bg-accent/90 inline-flex h-11 shrink-0 items-center justify-center rounded-lg px-5 text-sm font-medium text-white transition"
          >
            + Add Listing
          </Link>
        </section>

        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <section className="mt-8 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <p className="text-sm font-medium text-slate-500">Total Listings</p>

            <p className="mt-3 text-3xl font-semibold tracking-tight">
              {loading ? "—" : totalListings}
            </p>

            <p className="mt-1 text-sm text-slate-500">
              Properties you have listed
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <p className="text-sm font-medium text-slate-500">Total Leads</p>

            <p className="mt-3 text-3xl font-semibold tracking-tight">
              {loading ? "—" : totalLeads}
            </p>

            <p className="mt-1 text-sm text-slate-500">
              Leads generated from your listings
            </p>
          </div>
        </section>

        {!loading && totalListings === 0 && (
          <section className="mt-8 rounded-xl border border-dashed border-slate-300 p-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-xl">
              +
            </div>

            <h2 className="mt-4 text-lg font-semibold">
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
        )}
      </div>
    </main>
  );
}
