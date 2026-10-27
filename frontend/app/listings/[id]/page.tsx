"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  SearchX,
  Phone,
  MessageCircle,
  Star,
  ChevronRight,
  Train,
  Plane,
  ShoppingBag,
  GraduationCap,
  Hospital,
} from "lucide-react";
import { getListing, ListingResponse } from "@/lib/api/listings";
import { useRouter } from "next/navigation";
import AppHeader from "@/components/AppHeader";
import PropertyImage from "@/components/PropertyImage";

type ViewState = "loading" | "normal" | "error" | "not-found";

// Mock Fallback Data
const MOCK_AMENITIES = [
  "Swimming Pool",
  "Indoor Games",
  "Fully Equipped Gym",
  "24/7 Security",
  "Power Backup",
  "Clubhouse",
  "Children's Play Area",
  "Landscaped Gardens",
];

const MOCK_ACCESSIBILITY = [
  { name: "Grocery Store", distance: "0.5 km", icon: ShoppingBag },
  { name: "Railway Station", distance: "3.2 km", icon: Train },
  { name: "Airport", distance: "12.5 km", icon: Plane },
  { name: "International School", distance: "1.2 km", icon: GraduationCap },
  { name: "Multi-Specialty Hospital", distance: "2.0 km", icon: Hospital },
];

function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatPropertyType(
  propertyType: ListingResponse["property_type"],
): string {
  switch (propertyType) {
    case "flat":
      return "Flat";

    case "house_land":
      return "House / Land";

    default:
      return propertyType;
  }
}

function getRoomNumber(
  rooms: Record<string, unknown> | null,
  key: string,
): number | null {
  if (!rooms) {
    return null;
  }

  const value = rooms[key];

  if (typeof value === "number") {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);

    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  return null;
}

function formatNumber(value: number | null): string {
  if (value === null) {
    return "—";
  }

  return value.toLocaleString("en-IN");
}

function getAmenities(amenities: Record<string, unknown> | null): string[] {
  if (!amenities) {
    return [];
  }

  const items = amenities.items;

  if (Array.isArray(items)) {
    const parsed = items
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.trim())
      .filter(Boolean);

    if (parsed.length > 0) return parsed;
  }

  const parsedObject = Object.entries(amenities)
    .filter(([, value]) => {
      return value === true || typeof value === "string";
    })
    .map(([key, value]) => {
      if (typeof value === "string" && value.trim()) {
        return value;
      }

      return key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
    });

  return parsedObject;
}

function getApiStatus(error: unknown): number | null {
  if (!error || typeof error !== "object") {
    return null;
  }

  const possibleError = error as {
    status?: number;
    statusCode?: number;
    response?: {
      status?: number;
    };
  };

  return (
    possibleError.status ??
    possibleError.statusCode ??
    possibleError.response?.status ??
    null
  );
}

function getApiErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Couldn't load this property.";
}

function LoadingState() {
  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="h-6 w-44 animate-pulse rounded-lg bg-zinc-200" />
          <div className="h-72 w-full animate-pulse rounded-2xl bg-zinc-200 sm:h-96" />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <div className="h-8 w-3/4 animate-pulse rounded-lg bg-zinc-200" />

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="border-border h-24 animate-pulse rounded-xl border bg-zinc-100"
                  />
                ))}
              </div>

              <div className="border-border h-32 animate-pulse rounded-xl border bg-zinc-100" />
              <div className="border-border h-40 animate-pulse rounded-xl border bg-zinc-100" />
            </div>

            <div className="border-border h-56 animate-pulse rounded-xl border bg-zinc-100" />
          </div>
        </div>
      </main>
    </>
  );
}

function NotFoundState() {
  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft flex min-h-[calc(100vh-4rem)] items-center justify-center p-4">
        <div className="bg-surface border-border w-full max-w-md rounded-2xl border p-8 text-center shadow-sm">
          <div className="text-text-muted mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
            <SearchX className="h-6 w-6" />
          </div>

          <h1 className="text-text-primary text-2xl font-bold tracking-tight">
            Property not found
          </h1>

          <p className="text-text-secondary mt-2 text-sm">
            This listing may have been sold or taken down.
          </p>

          <div className="mt-6">
            <Link
              href="/customer"
              className="bg-accent hover:bg-accent-hover inline-flex w-full items-center justify-center rounded-xl px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors"
            >
              Browse other properties
            </Link>
          </div>
        </div>
      </main>
    </>
  );
}

function ErrorState({
  message,
  onRetry,
  isRetrying,
}: {
  message: string;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft flex min-h-[calc(100vh-4rem)] items-center justify-center p-4">
        <div className="bg-surface border-border w-full max-w-md rounded-2xl border p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-500">
            <AlertCircle className="h-6 w-6" />
          </div>

          <h1 className="text-text-primary text-2xl font-bold tracking-tight">
            Couldn&apos;t load this property
          </h1>

          <p className="text-text-secondary mt-2 text-sm">{message}</p>

          <div className="mt-6">
            <button
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
              className="bg-accent hover:bg-accent-hover inline-flex w-full items-center justify-center rounded-xl px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors disabled:opacity-75"
            >
              {isRetrying ? (
                <span className="inline-flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Retrying…
                </span>
              ) : (
                "Try again"
              )}
            </button>
          </div>
        </div>
      </main>
    </>
  );
}

export default function PropertyDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const [property, setProperty] = useState<ListingResponse | null>(null);

  const [viewState, setViewState] = useState<ViewState>("loading");

  const [errorMessage, setErrorMessage] = useState(
    "Check your connection and try again.",
  );

  const [isRetrying, setIsRetrying] = useState(false);

  const listingId = Number(resolvedParams.id);

  const loadProperty = useCallback(async () => {
    if (!Number.isInteger(listingId) || listingId <= 0) {
      setProperty(null);
      setViewState("not-found");
      return;
    }

    setViewState("loading");
    setErrorMessage("Check your connection and try again.");

    try {
      const data = await getListing(listingId);

      setProperty(data);
      setViewState("normal");
    } catch (error) {
      const status = getApiStatus(error);

      if (status === 404) {
        setProperty(null);
        setViewState("not-found");
        return;
      }

      setProperty(null);
      setErrorMessage(getApiErrorMessage(error));
      setViewState("error");
    }
  }, [listingId]);

  useEffect(() => {
    void loadProperty();
  }, [loadProperty]);

  const handleTryAgain = async () => {
    setIsRetrying(true);

    try {
      await loadProperty();
    } finally {
      setIsRetrying(false);
    }
  };

  if (viewState === "loading") {
    return <LoadingState />;
  }

  if (viewState === "not-found") {
    return <NotFoundState />;
  }

  if (viewState === "error") {
    return (
      <ErrorState
        message={errorMessage}
        onRetry={handleTryAgain}
        isRetrying={isRetrying}
      />
    );
  }

  if (!property) {
    return null;
  }

  const bedrooms = getRoomNumber(property.rooms, "bedrooms");
  const bathrooms = getRoomNumber(property.rooms, "bathrooms");

  const pricePerSqft =
    property.carpet_area && property.carpet_area > 0
      ? Math.round(property.price / property.carpet_area)
      : null;

  const fetchedAmenities = getAmenities(property.amenities);
  const amenitiesList =
    fetchedAmenities.length > 0 ? fetchedAmenities : MOCK_AMENITIES;
  const propertyImages =
    property.images?.map((image) => image.trim()).filter(Boolean) ?? [];

  const broker = (property as Record<string, any>).broker || {
    id: 1,
    name: "Jaydev Prajapati",
    years_experience: 8,
    active_listings: 14,
    properties_sold: 42,
    rating: 4.8,
    review_count: 29,
  };

  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] pb-28 lg:pb-8">
        <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => router.back()}
            className="text-text-secondary hover:text-text-primary group inline-flex items-center gap-2 text-sm font-medium transition-colors"
          >
            <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
          </button>

          <div className="space-y-3">
            <PropertyImage
              src={propertyImages[0]}
              alt={`${property.title} property photo`}
              className="h-64 w-full rounded-2xl border border-zinc-200 shadow-xs sm:h-96 dark:border-zinc-800"
              sizes="(max-width: 640px) 100vw, 960px"
              priority
            />

            {propertyImages.length > 1 && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {propertyImages.slice(1).map((image, index) => (
                  <PropertyImage
                    key={`${image}-${index + 1}`}
                    src={image}
                    alt={`${property.title} property photo ${index + 2}`}
                    className="aspect-video rounded-xl border border-zinc-200 shadow-xs dark:border-zinc-800"
                    sizes="(max-width: 640px) 50vw, 240px"
                  />
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <div>
                <h1 className="text-text-primary text-2xl font-bold tracking-tight sm:text-3xl">
                  {property.title}
                </h1>

                <div className="mt-2">
                  <span className="bg-accent-soft text-accent border-accent-border/30 inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold">
                    {formatPropertyType(property.property_type)}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
                {[
                  {
                    label: "Bedrooms",
                    value: bedrooms ?? "—",
                  },
                  {
                    label: "Bathrooms",
                    value: bathrooms ?? "—",
                  },
                  {
                    label: "Carpet area",
                    value:
                      property.carpet_area !== null
                        ? `${formatNumber(property.carpet_area)} sq ft`
                        : "—",
                  },
                  {
                    label: "Floor",
                    value: property.floor_number ?? "—",
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="bg-surface border-border rounded-xl border p-4 text-center"
                  >
                    <div className="text-text-primary text-lg font-bold sm:text-xl">
                      {item.value}
                    </div>

                    <div className="text-text-secondary mt-1 text-xs font-medium">
                      {item.label}
                    </div>
                  </div>
                ))}
              </div>

              {/* Description */}
              <section>
                <h2 className="text-text-primary mb-2 text-lg font-bold tracking-tight">
                  Description
                </h2>

                <p className="text-text-secondary text-base leading-relaxed">
                  {property.description || "No description available."}
                </p>
              </section>

              {property.video_tour_url && (
                <section>
                  <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                    Virtual tour
                  </h2>
                  <video
                    controls
                    preload="metadata"
                    className="w-full rounded-2xl border border-zinc-200 bg-black dark:border-zinc-800"
                  >
                    <source src={property.video_tour_url} />
                    Your browser does not support the video player.
                  </video>
                </section>
              )}

              {/* Broker Card */}
              <section>
                <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                  Listed By
                </h2>

                <Link
                  href={`/brokers/${broker.id}`}
                  className="bg-surface border-border hover:border-accent/40 group block rounded-2xl border p-5 shadow-sm transition-all hover:shadow-md"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 sm:gap-4">
                      <div className="bg-accent/10 text-accent flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full font-bold">
                        {broker.name.charAt(0)}
                      </div>

                      <div>
                        <div className="flex items-center gap-1.5">
                          <h3 className="text-text-primary group-hover:text-accent text-base font-bold transition-colors">
                            {broker.name}
                          </h3>
                        </div>

                        <div className="text-text-secondary mt-0.5 flex items-center gap-1 text-xs font-medium">
                          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                          <span className="text-text-primary font-semibold">
                            {broker.rating ?? 4.8}
                          </span>
                          <span>({broker.review_count ?? 0} reviews)</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-text-secondary group-hover:text-accent flex items-center gap-1 text-sm font-medium transition-colors">
                      <span className="hidden sm:inline">View Profile</span>
                      <ChevronRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </div>

                  <div className="border-border mt-4 grid grid-cols-3 gap-2 border-t pt-4 text-center">
                    <div>
                      <div className="text-text-primary text-sm font-bold sm:text-base">
                        {broker.years_experience ?? 0} yrs
                      </div>
                      <div className="text-text-secondary text-xs">
                        Experience
                      </div>
                    </div>

                    <div className="border-border border-x">
                      <div className="text-text-primary text-sm font-bold sm:text-base">
                        {broker.active_listings ?? 0}
                      </div>
                      <div className="text-text-secondary text-xs">
                        Listings
                      </div>
                    </div>

                    <div>
                      <div className="text-text-primary text-sm font-bold sm:text-base">
                        {broker.properties_sold ?? 0}
                      </div>
                      <div className="text-text-secondary text-xs">
                        Properties Sold
                      </div>
                    </div>
                  </div>
                </Link>
              </section>

              {/* Property Details */}
              <section>
                <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                  Details
                </h2>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {[
                    {
                      label: "Built-up area",
                      value:
                        property.built_up_area !== null
                          ? `${formatNumber(property.built_up_area)} sq ft`
                          : "—",
                    },
                    {
                      label: "Plot area",
                      value:
                        property.plot_area !== null
                          ? `${formatNumber(property.plot_area)} sq ft`
                          : "—",
                    },
                    {
                      label: "Price per sq ft",
                      value:
                        pricePerSqft !== null
                          ? `₹${formatNumber(pricePerSqft)}`
                          : "—",
                    },
                    {
                      label: "Property type",
                      value: formatPropertyType(property.property_type),
                    },
                  ].map((row) => (
                    <div
                      key={row.label}
                      className="bg-surface border-border flex items-center justify-between rounded-xl border p-3.5"
                    >
                      <span className="text-text-secondary text-sm font-medium">
                        {row.label}
                      </span>

                      <span className="text-text-primary text-sm font-semibold">
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              {/* Amenities Chips */}
              <section>
                <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                  Amenities
                </h2>

                <div className="flex flex-wrap gap-2">
                  {amenitiesList.map((amenity) => (
                    <span
                      key={amenity}
                      className="bg-surface border-border text-text-primary inline-flex items-center rounded-xl border px-3.5 py-2 text-xs font-semibold shadow-2xs sm:text-sm"
                    >
                      {amenity}
                    </span>
                  ))}
                </div>
              </section>

              {/* Accessibility / Nearby Places */}
              <section>
                <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                  Accessibility & Nearby Places
                </h2>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {MOCK_ACCESSIBILITY.map((item) => {
                    const IconComponent = item.icon;
                    return (
                      <div
                        key={item.name}
                        className="bg-surface border-border flex items-center justify-between rounded-xl border p-3.5"
                      >
                        <div className="flex items-center gap-3">
                          <div className="bg-surface-soft text-text-secondary flex h-9 w-9 items-center justify-center rounded-lg">
                            <IconComponent className="h-4 w-4" />
                          </div>

                          <span className="text-text-primary text-sm font-medium">
                            {item.name}
                          </span>
                        </div>

                        <span className="bg-accent-soft text-accent rounded-md px-2 py-1 text-xs font-semibold">
                          {item.distance}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
              <div className="bg-surface border-border rounded-2xl border p-5 shadow-sm">
                <div className="text-accent text-2xl font-extrabold tracking-tight">
                  {formatINR(property.price)}
                </div>

                {pricePerSqft !== null && (
                  <div className="text-text-secondary mt-0.5 text-xs">
                    ₹{formatNumber(pricePerSqft)} / sq ft
                  </div>
                )}

                <div className="border-border mt-5 flex flex-col gap-2.5 border-t pt-5">
                  <button
                    type="button"
                    className="bg-accent hover:bg-accent-hover shadow-accent/20 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white shadow-md transition-colors"
                  >
                    <Phone className="h-4 w-4" />
                    Contact Broker
                  </button>

                  <button
                    type="button"
                    className="text-text-primary bg-surface border-border hover:bg-surface-soft inline-flex items-center justify-center gap-2 rounded-xl border px-5 py-3 text-sm font-semibold transition-colors"
                  >
                    <MessageCircle className="h-4 w-4" />
                    Chat About This Property
                  </button>
                </div>
              </div>
            </aside>
          </div>
        </div>

        <div className="bg-surface border-border fixed inset-x-0 bottom-0 flex gap-2.5 border-t p-3 shadow-[0_-4px_16px_rgba(0,0,0,0.06)] lg:hidden">
          <button
            type="button"
            className="bg-accent inline-flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white"
          >
            <Phone className="h-4 w-4" />
            Call
          </button>

          <button
            type="button"
            className="text-text-primary bg-surface border-border inline-flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold"
          >
            <MessageCircle className="h-4 w-4" />
            Chat
          </button>
        </div>
      </main>
    </>
  );
}
