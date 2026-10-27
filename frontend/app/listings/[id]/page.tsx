"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  Bus,
  ChevronRight,
  GraduationCap,
  Hospital,
  Loader2,
  MapPin,
  MessageCircle,
  Phone,
  RefreshCw,
  SearchX,
  Share2,
  Sparkles,
  Star,
  Trees,
  UtensilsCrossed,
  X,
} from "lucide-react";
import AppHeader from "@/components/AppHeader";
import PropertyImage from "@/components/PropertyImage";
import GoogleMap from "@/components/map/GoogleMap";
import {
  formatINR,
  formatPriceShort,
  formatPropertyType,
  getListing,
  listingImageUrls,
  STATUS_LABELS,
  type Amenities,
  type Listing,
  type NearbyPlace,
} from "@/lib/api/listings";
import {
  contactBroker,
  getBrokerPublicProfile,
  getMyLead,
  type BrokerPublicProfile,
  type LeadCreateResponse,
} from "@/lib/api/broker";
import { errorMessage, isApiError } from "@/lib/api/client";
import { useAuthStore } from "@/stores/authStore";

type ViewState = "loading" | "normal" | "error" | "not-found";

const NEARBY_CATEGORIES: {
  key: string;
  label: string;
  icon: typeof GraduationCap;
}[] = [
  { key: "schools", label: "Schools", icon: GraduationCap },
  { key: "hospitals", label: "Hospitals", icon: Hospital },
  { key: "transit", label: "Transit", icon: Bus },
  { key: "restaurants", label: "Restaurants", icon: UtensilsCrossed },
  { key: "parks", label: "Parks", icon: Trees },
];

function formatDistance(metres: number): string {
  return metres < 1000
    ? `${Math.round(metres / 10) * 10} m`
    : `${(metres / 1000).toFixed(1)} km`;
}

function formatNumber(value: number | null): string {
  return value === null ? "—" : Math.round(value).toLocaleString("en-IN");
}

/** Monthly EMI for a home loan: P·r·(1+r)^n / ((1+r)^n − 1). */
function monthlyEmi(principal: number, annualRatePct: number, years: number) {
  const r = annualRatePct / 12 / 100;
  const n = years * 12;
  if (principal <= 0 || n <= 0) return 0;
  if (r === 0) return principal / n;
  const f = Math.pow(1 + r, n);
  return (principal * r * f) / (f - 1);
}

function nearbyGroups(amenities: Amenities | null) {
  if (!amenities) return [];
  return NEARBY_CATEGORIES.map((cat) => ({
    ...cat,
    places: (Array.isArray(amenities[cat.key]) ? amenities[cat.key] : [])
      .slice()
      .sort((a: NearbyPlace, b: NearbyPlace) => a.distance_m - b.distance_m)
      .slice(0, 3),
  })).filter((group) => group.places.length > 0);
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft flex min-h-[calc(100vh-4rem)] items-center justify-center p-4">
        <div className="bg-surface border-border w-full max-w-md rounded-2xl border p-8 text-center shadow-sm">
          {children}
        </div>
      </main>
    </>
  );
}

function LoadingState() {
  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl space-y-6" aria-busy="true">
          <div className="h-6 w-44 animate-pulse rounded-lg bg-zinc-200" />
          <div className="h-72 w-full animate-pulse rounded-2xl bg-zinc-200 sm:h-96" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-2">
              <div className="h-8 w-3/4 animate-pulse rounded-lg bg-zinc-200" />
              <div className="h-24 animate-pulse rounded-xl bg-zinc-100" />
              <div className="h-40 animate-pulse rounded-xl bg-zinc-100" />
            </div>
            <div className="h-56 animate-pulse rounded-xl bg-zinc-100" />
          </div>
        </div>
      </main>
    </>
  );
}

/** "Contact broker": optional message, then the broker's name and phone. */
function ContactDialog({
  listing,
  onClose,
}: {
  listing: Listing;
  onClose: () => void;
}) {
  const [message, setMessage] = useState(
    `Hi, I'm interested in "${listing.title}". Is it still available?`,
  );
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lead, setLead] = useState<LeadCreateResponse | null>(null);

  // A customer who already enquired sees the broker's details straight away.
  useEffect(() => {
    getMyLead(listing.id)
      .then(setLead)
      .catch(() => undefined);
  }, [listing.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function send() {
    setIsSending(true);
    setError(null);
    try {
      setLead(await contactBroker(listing.id, message.trim() || null));
    } catch (err) {
      if (isApiError(err, 409)) {
        try {
          setLead(await getMyLead(listing.id));
          return;
        } catch {
          // fall through to the original error
        }
      }
      setError(errorMessage(err, "Couldn't send your enquiry."));
    } finally {
      setIsSending(false);
    }
  }

  const phone = lead?.broker.phone ?? null;
  const whatsapp = phone
    ? `https://wa.me/${phone.replace(/\D/g, "")}?text=${encodeURIComponent(
        `Hi ${lead?.broker.name}, I'm interested in "${listing.title}" on Reality AI.`,
      )}`
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="contact-title"
      onClick={onClose}
    >
      <div
        className="bg-surface w-full max-w-md rounded-t-2xl p-6 shadow-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2
            id="contact-title"
            className="text-text-primary text-lg font-bold"
          >
            {lead ? "Broker contact" : "Contact the broker"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-text-muted hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {lead ? (
          <div className="mt-4 space-y-4">
            <p className="text-text-secondary text-sm">
              Your enquiry was sent to <strong>{lead.broker.name}</strong>. They
              can see your name and email and will get back to you.
            </p>
            {phone ? (
              <div className="grid grid-cols-2 gap-2">
                <a
                  href={`tel:${phone}`}
                  className="bg-accent hover:bg-accent-hover inline-flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white"
                >
                  <Phone className="h-4 w-4" />
                  {phone}
                </a>
                <a
                  href={whatsapp!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-3 text-sm font-semibold text-white hover:bg-[#1ebe5a]"
                >
                  <MessageCircle className="h-4 w-4" />
                  WhatsApp
                </a>
              </div>
            ) : (
              <p className="text-text-muted text-sm">
                This broker hasn&apos;t added a phone number yet.
              </p>
            )}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <label htmlFor="lead-message" className="sr-only">
              Your message
            </label>
            <textarea
              id="lead-message"
              rows={4}
              maxLength={2000}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="border-border focus:border-accent focus:ring-accent/10 w-full rounded-xl border px-3 py-2 text-sm outline-none focus:ring-4"
            />
            {error && (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            )}
            <button
              type="button"
              onClick={send}
              disabled={isSending}
              className="bg-accent hover:bg-accent-hover inline-flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {isSending && <Loader2 className="h-4 w-4 animate-spin" />}
              Send enquiry and show phone number
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function EmiEstimate({ price }: { price: number }) {
  const [downPct, setDownPct] = useState(20);
  const [rate, setRate] = useState(8.5);
  const [years, setYears] = useState(20);
  const emi = monthlyEmi(price * (1 - downPct / 100), rate, years);

  const field =
    "border-border w-full rounded-lg border px-2 py-1.5 text-sm outline-none focus:border-accent";

  return (
    <div className="bg-surface border-border rounded-2xl border p-5 shadow-sm">
      <h2 className="text-text-primary text-sm font-bold">EMI estimate</h2>
      <p className="text-accent mt-1 text-xl font-extrabold">
        {formatINR(Math.round(emi))}
        <span className="text-text-secondary text-xs font-medium">
          {" "}
          / month
        </span>
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <label className="text-text-secondary space-y-1">
          <span>Down %</span>
          <input
            type="number"
            min={0}
            max={90}
            value={downPct}
            onChange={(e) =>
              setDownPct(Math.min(90, Math.max(0, Number(e.target.value) || 0)))
            }
            className={field}
          />
        </label>
        <label className="text-text-secondary space-y-1">
          <span>Rate %</span>
          <input
            type="number"
            min={0}
            max={20}
            step={0.1}
            value={rate}
            onChange={(e) =>
              setRate(Math.min(20, Math.max(0, Number(e.target.value) || 0)))
            }
            className={field}
          />
        </label>
        <label className="text-text-secondary space-y-1">
          <span>Years</span>
          <input
            type="number"
            min={1}
            max={30}
            value={years}
            onChange={(e) =>
              setYears(Math.min(30, Math.max(1, Number(e.target.value) || 1)))
            }
            className={field}
          />
        </label>
      </div>
      <p className="text-text-muted mt-2 text-[11px]">
        An estimate only; your bank&apos;s offer may differ.
      </p>
    </div>
  );
}

export default function PropertyDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const user = useAuthStore((state) => state.user);
  const [property, setProperty] = useState<Listing | null>(null);
  const [broker, setBroker] = useState<BrokerPublicProfile | null>(null);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorText, setErrorText] = useState("");
  const [isRetrying, setIsRetrying] = useState(false);
  const [activeImage, setActiveImage] = useState(0);
  const [showContact, setShowContact] = useState(false);
  const [shareNote, setShareNote] = useState<string | null>(null);

  const listingId = Number(resolvedParams.id);

  const isValidId = Number.isInteger(listingId) && listingId > 0;

  // Bumped by "Try again" to fetch the listing again.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!isValidId) return;
    let cancelled = false;
    getListing(listingId)
      .then((data) => {
        if (cancelled) return;
        setProperty(data);
        setActiveImage(0);
        setViewState("normal");
        getBrokerPublicProfile(data.broker_id)
          .then((b) => !cancelled && setBroker(b))
          .catch(() => !cancelled && setBroker(null));
      })
      .catch((error) => {
        if (cancelled) return;
        setProperty(null);
        if (isApiError(error, 404)) {
          setViewState("not-found");
          return;
        }
        setErrorText(errorMessage(error, "Couldn't load this property."));
        setViewState("error");
      })
      .finally(() => !cancelled && setIsRetrying(false));
    return () => {
      cancelled = true;
    };
  }, [listingId, isValidId, reloadKey]);

  async function share() {
    if (!property) return;
    const url = window.location.href;
    const text = `${property.title} – ${formatPriceShort(property.price)}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: property.title, text, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setShareNote("Link copied");
    } catch {
      setShareNote(null);
    }
  }

  if (isValidId && viewState === "loading") return <LoadingState />;

  if (!isValidId || viewState === "not-found") {
    return (
      <PageShell>
        <div className="text-text-muted mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
          <SearchX className="h-6 w-6" />
        </div>
        <h1 className="text-text-primary text-2xl font-bold tracking-tight">
          Property not found
        </h1>
        <p className="text-text-secondary mt-2 text-sm">
          This listing may have been removed.
        </p>
        <Link
          href="/"
          className="bg-accent hover:bg-accent-hover mt-6 inline-flex w-full items-center justify-center rounded-xl px-5 py-2.5 text-sm font-medium text-white"
        >
          Search other properties
        </Link>
      </PageShell>
    );
  }

  if (viewState === "error" || !property) {
    return (
      <PageShell>
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-500">
          <AlertCircle className="h-6 w-6" />
        </div>
        <h1 className="text-text-primary text-2xl font-bold tracking-tight">
          Couldn&apos;t load this property
        </h1>
        <p className="text-text-secondary mt-2 text-sm">{errorText}</p>
        <button
          type="button"
          onClick={() => {
            setIsRetrying(true);
            setReloadKey((k) => k + 1);
          }}
          disabled={isRetrying}
          className="bg-accent hover:bg-accent-hover mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium text-white disabled:opacity-75"
        >
          {isRetrying && <RefreshCw className="h-4 w-4 animate-spin" />}
          Try again
        </button>
      </PageShell>
    );
  }

  const images = listingImageUrls(property);
  const bedrooms = property.rooms?.bedrooms ?? null;
  const bathrooms = property.rooms?.bathrooms ?? null;
  const pricePerSqft =
    property.carpet_area && property.carpet_area > 0
      ? Math.round(property.price / property.carpet_area)
      : null;
  const nearby = nearbyGroups(property.amenities);
  const isAvailable =
    property.status === "available" || property.status === "under_offer";
  const isOwner = user?.role === "broker" && user.id === property.broker_id;
  const similarQuery = [
    bedrooms ? `${bedrooms} BHK` : null,
    property.property_type === "flat" ? "flat" : "plot",
    `under ${formatPriceShort(property.price * 1.2).replace("₹", "")}`,
  ]
    .filter(Boolean)
    .join(" ");

  const contactButton = (() => {
    if (!isAvailable) {
      return (
        <p className="text-text-secondary rounded-xl bg-zinc-100 px-4 py-3 text-center text-sm">
          This property is {STATUS_LABELS[property.status].toLowerCase()}.
        </p>
      );
    }
    if (isOwner) {
      return (
        <Link
          href="/broker/dashboard"
          className="bg-accent hover:bg-accent-hover inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white"
        >
          Manage in your dashboard
        </Link>
      );
    }
    if (user?.role === "broker") return null;
    if (!user) {
      return (
        <Link
          href={`/login?redirect=${encodeURIComponent(`/listings/${property.id}`)}`}
          className="bg-accent hover:bg-accent-hover inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white"
        >
          <Phone className="h-4 w-4" />
          Log in to contact the broker
        </Link>
      );
    }
    return (
      <button
        type="button"
        onClick={() => setShowContact(true)}
        className="bg-accent hover:bg-accent-hover shadow-accent/20 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white shadow-md transition-colors"
      >
        <Phone className="h-4 w-4" />
        Contact broker
      </button>
    );
  })();

  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] pb-28 lg:pb-8">
        <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => router.back()}
              className="text-text-secondary hover:text-text-primary group inline-flex items-center gap-2 text-sm font-medium transition-colors"
            >
              <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
              Back
            </button>
            <button
              type="button"
              onClick={share}
              className="text-text-secondary hover:text-text-primary inline-flex items-center gap-2 text-sm font-medium"
            >
              <Share2 className="h-4 w-4" />
              {shareNote ?? "Share"}
            </button>
          </div>

          {/* Gallery */}
          <div className="space-y-3">
            <div className="relative">
              <PropertyImage
                src={images[activeImage]}
                alt={`${property.title} photo ${activeImage + 1}`}
                className="h-64 w-full rounded-2xl border border-zinc-200 shadow-xs sm:h-96"
                sizes="(max-width: 640px) 100vw, 960px"
                priority
              />
              {property.status !== "available" && (
                <span className="absolute top-3 left-3 rounded-lg bg-amber-500 px-3 py-1 text-xs font-semibold text-white">
                  {STATUS_LABELS[property.status]}
                </span>
              )}
            </div>
            {images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {images.map((src, index) => (
                  <button
                    key={src}
                    type="button"
                    onClick={() => setActiveImage(index)}
                    aria-label={`Show photo ${index + 1}`}
                    aria-current={index === activeImage}
                    className={`shrink-0 rounded-xl ${index === activeImage ? "ring-accent ring-2" : "opacity-80 hover:opacity-100"}`}
                  >
                    <PropertyImage
                      src={src}
                      alt=""
                      className="h-16 w-24 rounded-xl"
                      sizes="96px"
                    />
                  </button>
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
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="bg-accent-soft text-accent border-accent-border/30 inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold">
                    {formatPropertyType(property.property_type)}
                  </span>
                  <span className="text-text-muted text-xs">
                    Listed{" "}
                    {new Date(property.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
                {[
                  { label: "Bedrooms", value: bedrooms ?? "—" },
                  { label: "Bathrooms", value: bathrooms ?? "—" },
                  {
                    label:
                      property.property_type === "flat"
                        ? "Carpet area"
                        : "Plot area",
                    value:
                      (property.property_type === "flat"
                        ? property.carpet_area
                        : (property.plot_area ?? property.carpet_area)) !== null
                        ? `${formatNumber(
                            property.property_type === "flat"
                              ? property.carpet_area
                              : (property.plot_area ?? property.carpet_area),
                          )} sq ft`
                        : "—",
                  },
                  { label: "Floor", value: property.floor_number ?? "—" },
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

              <section>
                <h2 className="text-text-primary mb-2 text-lg font-bold tracking-tight">
                  Description
                </h2>
                <p className="text-text-secondary text-base leading-relaxed whitespace-pre-line">
                  {property.description || "No description provided."}
                </p>
              </section>

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
                      label: "Status",
                      value: STATUS_LABELS[property.status],
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

              <section>
                <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                  Nearby places
                </h2>
                {nearby.length > 0 ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {nearby.map(({ key, label, icon: Icon, places }) => (
                      <div
                        key={key}
                        className="bg-surface border-border rounded-xl border p-4"
                      >
                        <div className="text-text-primary mb-2 flex items-center gap-2 text-sm font-semibold">
                          <Icon className="text-accent h-4 w-4" />
                          {label}
                        </div>
                        <ul className="space-y-1.5">
                          {places.map((place) => (
                            <li
                              key={place.name}
                              className="flex items-center justify-between gap-3 text-sm"
                            >
                              <span className="text-text-secondary truncate">
                                {place.name}
                                {place.rating ? (
                                  <span className="text-text-muted ml-1 inline-flex items-center gap-0.5 text-xs">
                                    <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                                    {place.rating}
                                  </span>
                                ) : null}
                              </span>
                              <span className="bg-accent-soft text-accent shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold">
                                {formatDistance(place.distance_m)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-text-muted text-sm">
                    Nearby schools, hospitals and transit haven&apos;t been
                    loaded for this listing yet.
                  </p>
                )}
              </section>

              {property.lat !== null && property.lng !== null && (
                <section>
                  <h2 className="text-text-primary mb-3 flex items-center gap-2 text-lg font-bold tracking-tight">
                    <MapPin className="text-accent h-5 w-5" />
                    Location
                  </h2>
                  <div className="border-border h-64 overflow-hidden rounded-2xl border">
                    <GoogleMap listings={[property]} />
                  </div>
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${property.lat},${property.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent mt-2 inline-block text-sm font-medium hover:underline"
                  >
                    Open in Google Maps
                  </a>
                </section>
              )}

              {broker && (
                <section>
                  <h2 className="text-text-primary mb-3 text-lg font-bold tracking-tight">
                    Listed by
                  </h2>
                  <Link
                    href={`/brokers/${broker.id}`}
                    className="bg-surface border-border hover:border-accent/40 group flex items-center justify-between gap-4 rounded-2xl border p-5 shadow-sm transition-all hover:shadow-md"
                  >
                    <div className="flex items-center gap-3 sm:gap-4">
                      <div className="bg-accent/10 text-accent flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full font-bold">
                        {broker.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-text-primary group-hover:text-accent text-base font-bold transition-colors">
                          {broker.name}
                        </h3>
                        <p className="text-text-secondary mt-0.5 text-xs">
                          {broker.active_listings} active listing
                          {broker.active_listings === 1 ? "" : "s"} · on Reality
                          AI since{" "}
                          {new Date(broker.member_since).toLocaleDateString(
                            "en-IN",
                            { month: "short", year: "numeric" },
                          )}
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="text-text-secondary group-hover:text-accent h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                </section>
              )}
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
                  {contactButton}
                  {user?.role !== "broker" && (
                    <Link
                      href={`/?q=${encodeURIComponent(similarQuery)}`}
                      className="text-text-primary bg-surface border-border hover:bg-surface-soft inline-flex items-center justify-center gap-2 rounded-xl border px-5 py-3 text-sm font-semibold transition-colors"
                    >
                      <Sparkles className="h-4 w-4" />
                      Find similar properties
                    </Link>
                  )}
                </div>
              </div>
              <EmiEstimate price={property.price} />
            </aside>
          </div>
        </div>

        {/* Mobile action bar */}
        <div className="bg-surface border-border fixed inset-x-0 bottom-0 flex items-center gap-3 border-t p-3 shadow-[0_-4px_16px_rgba(0,0,0,0.06)] lg:hidden">
          <div className="min-w-0 flex-1">
            <div className="text-accent truncate text-lg font-extrabold">
              {formatPriceShort(property.price)}
            </div>
            <div className="text-text-muted truncate text-xs">
              {property.title}
            </div>
          </div>
          <div className="shrink-0">{contactButton}</div>
        </div>
      </main>

      {showContact && (
        <ContactDialog
          listing={property}
          onClose={() => setShowContact(false)}
        />
      )}
    </>
  );
}
