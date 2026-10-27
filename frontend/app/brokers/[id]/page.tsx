"use client";

import { use } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Star,
  Phone,
  Mail,
  Bed,
  Bath,
  Maximize2,
  MapPin,
} from "lucide-react";
import AppHeader from "@/components/AppHeader";

export interface BrokerListing {
  id: number;
  title: string;
  property_type: "flat" | "house_land";
  price: number;
  carpet_area: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  location: string;
  image_url: string;
}

export interface BrokerProfile {
  id: number;
  name: string;
  agency_name: string;
  avatar_url?: string;
  rating: number;
  review_count: number;
  years_experience: number;
  active_listings_count: number;
  properties_sold: number;
  phone: string;
  email: string;
  operating_areas: string[];
  bio: string;
  verified: boolean;
  listings: BrokerListing[];
}

const MOCK_BROKER: BrokerProfile = {
  id: 1,
  name: "Jaydev Prajapati",
  agency_name: "Apex Luxury Realty",
  avatar_url: "",
  rating: 4.8,
  review_count: 29,
  years_experience: 8,
  active_listings_count: 3,
  properties_sold: 42,
  phone: "+91 98765 43210",
  email: "jaydevprajapati@realityai.com",
  operating_areas: ["Bandra West", "Juhu", "Khar West", "Lower Parel"],
  bio: "Specializing in premium residential properties across South & West Mumbai for over 8 years. Dedicated to providing transparent transactions, thorough property verification, and tailored real estate solutions.",
  verified: true,
  listings: [
    {
      id: 2,
      title: "3 BHK Luxury Apartment in Heights",
      property_type: "flat",
      price: 24500000,
      carpet_area: 1450,
      bedrooms: 3,
      bathrooms: 3,
      location: "Bandra West, Mumbai",
      image_url:
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
    },
    {
      id: 3,
      title: "Modern 2 BHK Sea Facing Flat",
      property_type: "flat",
      price: 18000000,
      carpet_area: 980,
      bedrooms: 2,
      bathrooms: 2,
      location: "Juhu, Mumbai",
      image_url:
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
    },
    {
      id: 4,
      title: "Independent Villa / Plot Land",
      property_type: "house_land",
      price: 45000000,
      carpet_area: 3200,
      bedrooms: 4,
      bathrooms: 5,
      location: "Khar West, Mumbai",
      image_url:
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
    },
  ],
};

function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatPropertyType(type: BrokerListing["property_type"]): string {
  switch (type) {
    case "flat":
      return "Flat";
    case "house_land":
      return "House / Land";
    default:
      return type;
  }
}

export default function BrokerDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);

  const broker = MOCK_BROKER;

  return (
    <>
      <AppHeader />
      <main className="bg-surface-soft min-h-[calc(100vh-4rem)] pb-12">
        <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => router.back()}
            className="text-text-secondary hover:text-text-primary group inline-flex items-center gap-2 text-sm font-medium transition-colors"
          >
            <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
            <span>Back</span>
          </button>

          <section className="bg-surface border-border rounded-2xl border p-6 shadow-sm">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <div className="bg-accent/10 text-accent relative flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold">
                  {broker.avatar_url ? (
                    <Image
                      src={broker.avatar_url}
                      alt={broker.name}
                      fill
                      className="object-cover"
                    />
                  ) : (
                    broker.name.charAt(0)
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-text-primary text-2xl font-bold tracking-tight">
                      {broker.name}
                    </h1>
                  </div>

                  <p className="text-text-secondary mt-0.5 text-sm font-medium">
                    {broker.agency_name}
                  </p>

                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs font-medium">
                    <div className="flex items-center gap-1 text-amber-500">
                      <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                      <span className="text-text-primary font-bold">
                        {broker.rating}
                      </span>
                      <span className="text-text-secondary">
                        ({broker.review_count} reviews)
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2.5 sm:w-48">
                <a
                  href={`tel:${broker.phone}`}
                  className="bg-accent hover:bg-accent-hover shadow-accent/20 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-md transition-colors"
                >
                  <Phone className="h-4 w-4" />
                  Call Broker
                </a>

                <a
                  href={`mailto:${broker.email}`}
                  className="text-text-primary bg-surface border-border hover:bg-surface-soft inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors"
                >
                  <Mail className="h-4 w-4" />
                  Send Email
                </a>
              </div>
            </div>

            <div className="border-border mt-6 grid grid-cols-3 gap-2 border-t pt-6 text-center">
              <div>
                <div className="text-text-primary text-lg font-bold sm:text-xl">
                  {broker.active_listings_count}
                </div>
                <div className="text-text-secondary mt-0.5 text-xs font-medium">
                  Active Listings
                </div>
              </div>

              <div className="border-border border-x">
                <div className="text-text-primary text-lg font-bold sm:text-xl">
                  {broker.properties_sold}
                </div>
                <div className="text-text-secondary mt-0.5 text-xs font-medium">
                  Properties Sold
                </div>
              </div>

              <div>
                <div className="text-text-primary text-lg font-bold sm:text-xl">
                  {broker.years_experience}+
                </div>
                <div className="text-text-secondary mt-0.5 text-xs font-medium">
                  Years Exp.
                </div>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-text-primary text-xl font-bold tracking-tight">
                Listings by {broker.name.split(" ")[0]}
              </h2>
              <span className="text-text-secondary text-xs font-semibold">
                {broker.listings.length} Available
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {broker.listings.map((item) => (
                <Link
                  key={item.id}
                  href={`/listings/${item.id}`}
                  className="bg-surface border-border hover:border-accent/40 group overflow-hidden rounded-2xl border shadow-xs transition-all hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="relative h-48 w-full bg-zinc-100">
                    <Image
                      src={item.image_url}
                      alt={item.title}
                      fill
                      className="object-cover transition-transform duration-300 group-hover:scale-105"
                      unoptimized
                    />
                    <div className="absolute top-3 left-3">
                      <span className="bg-surface/90 text-text-primary border-border/50 rounded-lg border px-2.5 py-1 text-xs font-semibold shadow-xs backdrop-blur-xs">
                        {formatPropertyType(item.property_type)}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-3 p-4">
                    <div>
                      <div className="text-accent text-lg font-extrabold tracking-tight">
                        {formatINR(item.price)}
                      </div>
                      <h3 className="text-text-primary group-hover:text-accent mt-0.5 line-clamp-1 text-base font-bold transition-colors">
                        {item.title}
                      </h3>
                      <p className="text-text-secondary mt-1 flex items-center gap-1 text-xs font-medium">
                        <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">{item.location}</span>
                      </p>
                    </div>

                    <div className="border-border text-text-secondary flex items-center justify-between border-t pt-3 text-xs font-medium">
                      {item.bedrooms !== null && (
                        <div className="flex items-center gap-1">
                          <Bed className="h-3.5 w-3.5" />
                          <span>{item.bedrooms} Beds</span>
                        </div>
                      )}

                      {item.bathrooms !== null && (
                        <div className="flex items-center gap-1">
                          <Bath className="h-3.5 w-3.5" />
                          <span>{item.bathrooms} Baths</span>
                        </div>
                      )}

                      {item.carpet_area !== null && (
                        <div className="flex items-center gap-1">
                          <Maximize2 className="h-3.5 w-3.5" />
                          <span>{item.carpet_area} sq ft</span>
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
