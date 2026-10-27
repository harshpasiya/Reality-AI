"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Bed, Building2, Maximize2, SearchX } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PropertyImage from "@/components/PropertyImage";
import {
  getBrokerPublicProfile,
  type BrokerPublicProfile,
} from "@/lib/api/broker";
import { errorMessage, isApiError } from "@/lib/api/client";
import {
  formatPriceShort,
  formatPropertyType,
  listingImageUrls,
  STATUS_LABELS,
} from "@/lib/api/listings";

export default function BrokerProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const { id } = use(params);
  const brokerId = Number(id);
  const isValidId = Number.isInteger(brokerId) && brokerId > 0;
  const [profile, setProfile] = useState<BrokerPublicProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const error = isValidId ? loadError : "This broker doesn't exist.";

  useEffect(() => {
    if (!isValidId) return;
    getBrokerPublicProfile(brokerId)
      .then(setProfile)
      .catch((err) =>
        setLoadError(
          isApiError(err, 404)
            ? "This broker doesn't exist."
            : errorMessage(err, "Couldn't load this broker."),
        ),
      );
  }, [brokerId, isValidId]);

  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] pb-12">
        <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => router.back()}
            className="text-text-secondary hover:text-text-primary inline-flex items-center gap-2 text-sm font-medium"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          {error ? (
            <div className="bg-surface border-border mx-auto max-w-md rounded-2xl border p-8 text-center">
              <SearchX className="text-text-muted mx-auto mb-3 h-8 w-8" />
              <p className="text-text-primary font-semibold">{error}</p>
              <Link
                href="/"
                className="text-accent mt-4 inline-block text-sm font-medium"
              >
                Search properties
              </Link>
            </div>
          ) : !profile ? (
            <div className="space-y-4" aria-busy="true">
              <div className="h-28 animate-pulse rounded-2xl bg-zinc-200" />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-64 animate-pulse rounded-2xl bg-zinc-100"
                  />
                ))}
              </div>
            </div>
          ) : (
            <>
              <section className="bg-surface border-border flex items-center gap-4 rounded-2xl border p-6 shadow-sm">
                <div className="bg-accent/10 text-accent flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-2xl font-bold">
                  {profile.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h1 className="text-text-primary text-2xl font-bold tracking-tight">
                    {profile.name}
                  </h1>
                  <p className="text-text-secondary mt-1 text-sm">
                    Broker in Surat · on Reality AI since{" "}
                    {new Date(profile.member_since).toLocaleDateString(
                      "en-IN",
                      { month: "long", year: "numeric" },
                    )}
                  </p>
                  <p className="text-text-secondary mt-0.5 text-sm">
                    {profile.active_listings} active listing
                    {profile.active_listings === 1 ? "" : "s"}
                  </p>
                </div>
              </section>

              <section>
                <h2 className="text-text-primary mb-4 text-lg font-bold tracking-tight">
                  Listings
                </h2>
                {profile.listings.length === 0 ? (
                  <p className="text-text-muted text-sm">
                    No properties are listed right now.
                  </p>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {profile.listings.map((item) => (
                      <Link
                        key={item.id}
                        href={`/listings/${item.id}`}
                        className="bg-surface border-border hover:border-accent/40 group overflow-hidden rounded-2xl border shadow-sm transition-all hover:shadow-md"
                      >
                        <div className="relative">
                          <PropertyImage
                            src={listingImageUrls(item)[0]}
                            alt={`${item.title} photo`}
                            className="h-44 w-full"
                            sizes="(max-width: 640px) 100vw, 320px"
                          />
                          {item.status === "under_offer" && (
                            <span className="absolute top-2 left-2 rounded-md bg-amber-500 px-2 py-0.5 text-xs font-semibold text-white">
                              {STATUS_LABELS.under_offer}
                            </span>
                          )}
                        </div>
                        <div className="space-y-2 p-4">
                          <div className="text-accent text-lg font-extrabold">
                            {formatPriceShort(item.price)}
                          </div>
                          <h3 className="text-text-primary group-hover:text-accent line-clamp-1 text-sm font-semibold">
                            {item.title}
                          </h3>
                          <div className="text-text-secondary flex flex-wrap items-center gap-3 text-xs">
                            <span className="flex items-center gap-1">
                              <Building2 className="h-3.5 w-3.5" />
                              {formatPropertyType(item.property_type)}
                            </span>
                            {item.rooms?.bedrooms ? (
                              <span className="flex items-center gap-1">
                                <Bed className="h-3.5 w-3.5" />
                                {item.rooms.bedrooms} BHK
                              </span>
                            ) : null}
                            {item.carpet_area ? (
                              <span className="flex items-center gap-1">
                                <Maximize2 className="h-3.5 w-3.5" />
                                {Math.round(item.carpet_area).toLocaleString(
                                  "en-IN",
                                )}{" "}
                                sq ft
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </>
  );
}
