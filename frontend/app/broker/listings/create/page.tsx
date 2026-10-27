"use client";

import { useState, FormEvent, ChangeEvent, FocusEvent, ReactNode } from "react";
import { ArrowLeft, ExternalLink, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  createListing,
  ListingResponse,
  CreateListingRequest,
  BackendPropertyType,
  extractListingDetails,
  uploadListingImage,
  uploadListingVideo,
} from "@/lib/api/listings";
import Link from "next/link";
import AppHeader from "@/components/AppHeader";

export interface CreateListingFormData {
  title: string;
  description: string;
  property_type: BackendPropertyType | "";
  price: string;
  bedrooms: string;
  bathrooms: string;
  floor_number: string;
  carpet_area: string;
  built_up_area: string;
  plot_area: string;
  lat: string;
  lng: string;
}

type FormErrors = Partial<Record<keyof CreateListingFormData, string>>;
type FormTouched = Partial<Record<keyof CreateListingFormData, boolean>>;

const INITIAL_FORM_DATA: CreateListingFormData = {
  title: "",
  description: "",
  property_type: "",
  price: "",
  bedrooms: "",
  bathrooms: "",
  floor_number: "",
  carpet_area: "",
  built_up_area: "",
  plot_area: "",
  lat: "",
  lng: "",
};

const SAMPLE_PROPERTY_DESCRIPTION =
  "Independent 3-bedroom house for sale in Andheri East, Mumbai, priced at INR 18,000,000. It has 3 bedrooms and 2 bathrooms on the ground floor, with 1,200 sq ft carpet area, 1,500 sq ft built-up area, and a 1,800 sq ft plot. Coordinates: latitude 19.1197, longitude 72.8468.";

function validateField(
  name: keyof CreateListingFormData,
  value: string,
  data: CreateListingFormData,
): string | undefined {
  switch (name) {
    case "title":
      if (!value.trim()) return "Property title is required";
      if (value.trim().length < 5) {
        return "Title must be at least 5 characters";
      }
      return;

    case "description":
      if (!value.trim()) return "Description is required";
      if (value.trim().length < 20) {
        return "Description must be at least 20 characters";
      }
      return;

    case "property_type":
      if (!value) return "Please select a property type";
      return;

    case "price": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n <= 0) {
        return "Please enter a valid positive price";
      }

      return;
    }

    case "bedrooms": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n < 0 || !Number.isInteger(n)) {
        return "Please enter a valid number of bedrooms";
      }

      return;
    }

    case "bathrooms": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n < 0 || !Number.isInteger(n)) {
        return "Please enter a valid number of bathrooms";
      }

      return;
    }

    case "floor_number": {
      if (!value && value !== "0") {
        return "Floor number is required";
      }

      const n = Number(value);

      if (Number.isNaN(n) || !Number.isInteger(n)) {
        return "Please enter a valid floor number";
      }

      return;
    }

    case "carpet_area": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n <= 0) {
        return "Please enter a valid carpet area";
      }

      return;
    }

    case "built_up_area": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n <= 0) {
        return "Please enter a valid built-up area";
      }

      if (data.carpet_area && n < Number(data.carpet_area)) {
        return "Built-up area cannot be less than carpet area";
      }

      return;
    }

    case "plot_area": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n <= 0) {
        return "Please enter a valid plot area";
      }

      return;
    }

    case "lat": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n < -90 || n > 90) {
        return "Latitude must be between -90 and 90";
      }

      return;
    }

    case "lng": {
      const n = Number(value);

      if (!value || Number.isNaN(n) || n < -180 || n > 180) {
        return "Longitude must be between -180 and 180";
      }

      return;
    }

    default:
      return;
  }
}

function validateForm(data: CreateListingFormData): FormErrors {
  const errors: FormErrors = {};

  (Object.keys(data) as Array<keyof CreateListingFormData>).forEach((field) => {
    const error = validateField(field, data[field], data);

    if (error) {
      errors[field] = error;
    }
  });

  return errors;
}

function toCreateListingRequest(
  data: CreateListingFormData,
): CreateListingRequest {
  if (!data.property_type) {
    throw new Error("Please select a property type.");
  }

  return {
    title: data.title.trim(),

    description: data.description.trim() || null,

    price: Number(data.price),

    property_type: data.property_type,

    carpet_area: Number(data.carpet_area),

    built_up_area: Number(data.built_up_area),

    plot_area: Number(data.plot_area),

    floor_number: Number(data.floor_number),

    rooms: {
      bedrooms: Number(data.bedrooms),
      bathrooms: Number(data.bathrooms),
    },

    lat: Number(data.lat),

    lng: Number(data.lng),

    images: [],

    video_tour_url: null,
  };
}

function formatPrice(val: string) {
  const num = Number(val);

  if (Number.isNaN(num)) {
    return val;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(num);
}

function getApiErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Unable to create listing. Please try again.";
}

const inputClass = (hasError: boolean) =>
  `w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 dark:bg-zinc-900 dark:text-zinc-100 ${
    hasError
      ? "border-red-500 focus:ring-4 focus:ring-red-500/10"
      : "border-zinc-300 focus:border-blue-600 focus:ring-4 focus:ring-blue-600/10 dark:border-zinc-700"
  }`;

type FieldProps = {
  label: string;
  name: keyof CreateListingFormData;
  error?: string;
  children: ReactNode;
  hint?: string;
  className?: string;
};

function Field({ label, name, error, children, hint, className }: FieldProps) {
  return (
    <div className={`space-y-1 ${className ?? ""}`}>
      <label
        htmlFor={name}
        className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
      >
        {label} <span className="text-red-500">*</span>
      </label>

      {children}

      {hint && !error && <p className="text-xs text-zinc-500">{hint}</p>}

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}

export default function BrokerCreateListingPage() {
  const router = useRouter();
  const [formData, setFormData] =
    useState<CreateListingFormData>(INITIAL_FORM_DATA);

  const [propertyDescription, setPropertyDescription] = useState("");
  const [hasStartedForm, setHasStartedForm] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<FormTouched>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [selectedImages, setSelectedImages] = useState<File[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<File | null>(null);

  const [submitError, setSubmitError] = useState<string | null>(null);

  const [createdListing, setCreatedListing] = useState<ListingResponse | null>(
    null,
  );

  const handleExtractDetails = async () => {
    setExtractionError(null);

    if (!propertyDescription.trim()) {
      setExtractionError("Describe the property before continuing.");
      return;
    }

    setIsExtracting(true);

    try {
      const result = await extractListingDetails(propertyDescription);

      if (!result.formData) {
        throw new Error(
          result.error || "The property details could not be extracted.",
        );
      }

      setFormData({ ...INITIAL_FORM_DATA, ...result.formData });
      setErrors({});
      setTouched({});
      setHasStartedForm(true);
    } catch (error) {
      setExtractionError(getApiErrorMessage(error));
    } finally {
      setIsExtracting(false);
    }
  };

  const handleChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;

    const field = name as keyof CreateListingFormData;

    const updated: CreateListingFormData = {
      ...formData,
      [field]: value,
    };

    setFormData(updated);

    setSubmitError(null);
    setIsSuccess(false);

    if (touched[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: validateField(field, value, updated),
      }));
    }

    if (field === "carpet_area" && touched.built_up_area) {
      setErrors((prev) => ({
        ...prev,
        built_up_area: validateField(
          "built_up_area",
          updated.built_up_area,
          updated,
        ),
      }));
    }

    if (field === "built_up_area" && touched.carpet_area) {
      setErrors((prev) => ({
        ...prev,
        carpet_area: validateField("carpet_area", updated.carpet_area, updated),
      }));
    }
  };

  const handleBlur = (
    e: FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;

    const field = name as keyof CreateListingFormData;

    setTouched((prev) => ({
      ...prev,
      [field]: true,
    }));

    setErrors((prev) => ({
      ...prev,
      [field]: validateField(field, value, formData),
    }));
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    setSubmitError(null);
    setIsSuccess(false);

    const allTouched: FormTouched = {};

    (Object.keys(formData) as Array<keyof CreateListingFormData>).forEach(
      (key) => {
        allTouched[key] = true;
      },
    );

    setTouched(allTouched);

    const validationErrors = validateForm(formData);

    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      const firstErrorKey = Object.keys(
        validationErrors,
      )[0] as keyof CreateListingFormData;

      document.getElementById(firstErrorKey)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });

      return;
    }

    setIsLoading(true);

    try {
      if (
        selectedImages.some((file) => !/\.(jpe?g|png|webp)$/i.test(file.name))
      ) {
        throw new Error("Property photos must be JPG, PNG, or WEBP files.");
      }

      if (selectedVideo && !/\.(mp4|webm)$/i.test(selectedVideo.name)) {
        throw new Error("The virtual tour must be an MP4 or WEBM file.");
      }

      const images = await Promise.all(
        selectedImages.map(async (file) => {
          const upload = await uploadListingImage(file);
          return upload.url;
        }),
      );
      const videoTourUrl = selectedVideo
        ? await uploadListingVideo(selectedVideo)
        : null;
      const payload: CreateListingRequest = {
        ...toCreateListingRequest(formData),
        images,
        video_tour_url: videoTourUrl,
      };

      const listing = await createListing(payload);

      setCreatedListing(listing);
      setIsSuccess(true);

      setFormData(INITIAL_FORM_DATA);
      setSelectedImages([]);
      setSelectedVideo(null);
      setErrors({});
      setTouched({});
      setSubmitError(null);

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } catch (error) {
      setSubmitError(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <AppHeader />
      <main className="min-h-[calc(100vh-4rem)] bg-zinc-50 px-4 py-10 text-zinc-900 sm:px-6 dark:bg-zinc-950 dark:text-zinc-100">
        <div className="mx-auto max-w-3xl">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold">
              {hasStartedForm
                ? "Review Property Details"
                : "Create New Listing"}
            </h1>

            <p className="mt-1 text-sm text-zinc-500">
              {hasStartedForm
                ? "Check the details Gemini filled in, then complete anything that is missing."
                : "Describe the property in your own words and Gemini will fill in the listing form."}
            </p>
          </div>

          {isSuccess && createdListing && (
            <div className="mb-6 flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-400">
              <p>Listing created successfully.</p>

              <Link
                href={`/listings/${createdListing.id}`}
                aria-label="View listing"
                title="View listing"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-green-700 transition-colors hover:bg-green-100 dark:text-green-400 dark:hover:bg-green-900/50"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            </div>
          )}

          {submitError && (
            <div
              role="alert"
              className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400"
            >
              {submitError}
            </div>
          )}

          {!hasStartedForm && (
            <section className="space-y-5 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-blue-50 p-2 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                  <Sparkles className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="font-medium">Describe the property</h2>
                  <p className="mt-1 text-sm text-zinc-500">
                    Include what you know, such as the property type, price,
                    rooms, floor, areas, and location. Details you don&apos;t
                    mention will be left for you to fill in.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setPropertyDescription(SAMPLE_PROPERTY_DESCRIPTION);
                      setExtractionError(null);
                    }}
                    disabled={isExtracting}
                    className="mt-2 text-sm font-medium text-blue-700 hover:text-blue-800 disabled:opacity-50 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    Try an example
                  </button>
                </div>
              </div>

              <textarea
                id="property-description"
                rows={6}
                maxLength={4000}
                value={propertyDescription}
                onChange={(event) => {
                  setPropertyDescription(event.target.value);
                  setExtractionError(null);
                }}
                placeholder="For example: A spacious 3 BHK apartment in Bandra, Mumbai, on the 5th floor. It has 1,150 sq ft carpet area, 1,420 sq ft built-up area, 2 bathrooms, and is priced at ₹2.4 crore..."
                className={`${inputClass(!!extractionError)} resize-y`}
                aria-describedby={
                  extractionError ? "extraction-error" : "description-limit"
                }
                aria-invalid={!!extractionError}
              />

              <div className="flex items-center justify-between gap-4">
                <p
                  id={
                    extractionError ? "extraction-error" : "description-limit"
                  }
                  className={`text-xs ${
                    extractionError
                      ? "text-red-600 dark:text-red-400"
                      : "text-zinc-500"
                  }`}
                  role={extractionError ? "alert" : undefined}
                >
                  {extractionError ??
                    `${propertyDescription.length}/4000 characters`}
                </p>
                <button
                  type="button"
                  onClick={handleExtractDetails}
                  disabled={isExtracting}
                  className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isExtracting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  {isExtracting ? "Filling in details..." : "Continue with AI"}
                </button>
              </div>

              <div className="border-t border-zinc-200 pt-4 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => {
                    setExtractionError(null);
                    setHasStartedForm(true);
                  }}
                  disabled={isExtracting}
                  className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 disabled:opacity-50 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Enter details manually
                </button>
              </div>
            </section>
          )}

          <form
            onSubmit={handleSubmit}
            noValidate
            hidden={!hasStartedForm}
            className="space-y-8"
          >
            <div className="space-y-4">
              <Field
                label="Property Title"
                name="title"
                error={touched.title ? errors.title : undefined}
              >
                <input
                  id="title"
                  name="title"
                  value={formData.title}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. Elegant 3 BHK Apartment with Skyline View"
                  className={inputClass(!!(touched.title && errors.title))}
                />
              </Field>

              <Field
                label="Description"
                name="description"
                error={touched.description ? errors.description : undefined}
              >
                <textarea
                  id="description"
                  name="description"
                  rows={4}
                  value={formData.description}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="Describe key highlights, features, and neighborhood advantages..."
                  className={`${inputClass(
                    !!(touched.description && errors.description),
                  )} resize-y`}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Property Type"
                name="property_type"
                error={touched.property_type ? errors.property_type : undefined}
              >
                <select
                  id="property_type"
                  name="property_type"
                  value={formData.property_type}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  className={inputClass(
                    !!(touched.property_type && errors.property_type),
                  )}
                >
                  <option value="" disabled>
                    Select property type
                  </option>

                  <option value="flat">Flat</option>

                  <option value="house_land">House / Land</option>
                </select>
              </Field>

              <Field
                label="Price (INR)"
                name="price"
                error={touched.price ? errors.price : undefined}
                hint={
                  formData.price && !errors.price
                    ? formatPrice(formData.price)
                    : undefined
                }
              >
                <input
                  type="number"
                  id="price"
                  name="price"
                  min="0"
                  step="1000"
                  value={formData.price}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 8500000"
                  className={inputClass(!!(touched.price && errors.price))}
                />
              </Field>

              <Field
                label="Bedrooms"
                name="bedrooms"
                error={touched.bedrooms ? errors.bedrooms : undefined}
              >
                <input
                  type="number"
                  id="bedrooms"
                  name="bedrooms"
                  min="0"
                  max="50"
                  step="1"
                  value={formData.bedrooms}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 3"
                  className={inputClass(
                    !!(touched.bedrooms && errors.bedrooms),
                  )}
                />
              </Field>

              <Field
                label="Bathrooms"
                name="bathrooms"
                error={touched.bathrooms ? errors.bathrooms : undefined}
              >
                <input
                  type="number"
                  id="bathrooms"
                  name="bathrooms"
                  min="0"
                  max="50"
                  step="1"
                  value={formData.bathrooms}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 2"
                  className={inputClass(
                    !!(touched.bathrooms && errors.bathrooms),
                  )}
                />
              </Field>

              <Field
                label="Floor Number"
                name="floor_number"
                error={touched.floor_number ? errors.floor_number : undefined}
              >
                <input
                  type="number"
                  id="floor_number"
                  name="floor_number"
                  min="-5"
                  max="200"
                  step="1"
                  value={formData.floor_number}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 5 (0 for Ground)"
                  className={inputClass(
                    !!(touched.floor_number && errors.floor_number),
                  )}
                />
              </Field>

              <Field
                label="Carpet Area (sq ft)"
                name="carpet_area"
                error={touched.carpet_area ? errors.carpet_area : undefined}
              >
                <input
                  type="number"
                  id="carpet_area"
                  name="carpet_area"
                  min="0"
                  step="any"
                  value={formData.carpet_area}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 1150"
                  className={inputClass(
                    !!(touched.carpet_area && errors.carpet_area),
                  )}
                />
              </Field>

              <Field
                label="Built-up Area (sq ft)"
                name="built_up_area"
                error={touched.built_up_area ? errors.built_up_area : undefined}
              >
                <input
                  type="number"
                  id="built_up_area"
                  name="built_up_area"
                  min="0"
                  step="any"
                  value={formData.built_up_area}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 1420"
                  className={inputClass(
                    !!(touched.built_up_area && errors.built_up_area),
                  )}
                />
              </Field>

              <Field
                label="Plot Area (sq ft)"
                name="plot_area"
                error={touched.plot_area ? errors.plot_area : undefined}
              >
                <input
                  type="number"
                  id="plot_area"
                  name="plot_area"
                  min="0"
                  step="any"
                  value={formData.plot_area}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 1800"
                  className={inputClass(
                    !!(touched.plot_area && errors.plot_area),
                  )}
                />
              </Field>

              <Field
                label="Latitude"
                name="lat"
                error={touched.lat ? errors.lat : undefined}
              >
                <input
                  type="number"
                  step="any"
                  id="lat"
                  name="lat"
                  value={formData.lat}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 19.0760"
                  className={inputClass(!!(touched.lat && errors.lat))}
                />
              </Field>

              <Field
                label="Longitude"
                name="lng"
                error={touched.lng ? errors.lng : undefined}
              >
                <input
                  type="number"
                  step="any"
                  id="lng"
                  name="lng"
                  value={formData.lng}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="e.g. 72.8777"
                  className={inputClass(!!(touched.lng && errors.lng))}
                />
              </Field>
            </div>

            <section className="space-y-5 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <div>
                <h2 className="text-sm font-semibold">Property media</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Add photos and an optional virtual tour video.
                </p>
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="listing-images"
                  className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
                >
                  Property photos
                </label>
                <input
                  id="listing-images"
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                  multiple
                  disabled={isLoading}
                  onChange={(event) => {
                    const files = Array.from(event.currentTarget.files ?? []);
                    setSelectedImages((previous) => [...previous, ...files]);
                    event.currentTarget.value = "";
                    setSubmitError(null);
                  }}
                  className="block w-full text-sm text-zinc-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100 dark:text-zinc-400 dark:file:bg-blue-950/50 dark:file:text-blue-300"
                />
                <p className="text-xs text-zinc-500">
                  Select one or more JPG, PNG, or WEBP images.
                </p>
                {selectedImages.length > 0 && (
                  <ul className="space-y-1">
                    {selectedImages.map((file, index) => (
                      <li
                        key={`${file.name}-${file.lastModified}-${index}`}
                        className="flex items-center justify-between gap-3 rounded-md bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-800"
                      >
                        <span className="truncate">{file.name}</span>
                        <button
                          type="button"
                          disabled={isLoading}
                          onClick={() =>
                            setSelectedImages((previous) =>
                              previous.filter(
                                (_, fileIndex) => fileIndex !== index,
                              ),
                            )
                          }
                          className="shrink-0 text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-50 dark:text-red-400"
                          aria-label={`Remove ${file.name}`}
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="listing-video"
                  className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
                >
                  Virtual tour video
                </label>
                <input
                  id="listing-video"
                  type="file"
                  accept=".mp4,.webm,video/mp4,video/webm"
                  disabled={isLoading}
                  onChange={(event) => {
                    setSelectedVideo(event.currentTarget.files?.[0] ?? null);
                    event.currentTarget.value = "";
                    setSubmitError(null);
                  }}
                  className="block w-full text-sm text-zinc-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100 dark:text-zinc-400 dark:file:bg-blue-950/50 dark:file:text-blue-300"
                />
                <p className="text-xs text-zinc-500">
                  Optional. Choose one MP4 or WEBM video.
                </p>
                {selectedVideo && (
                  <div className="flex items-center justify-between gap-3 rounded-md bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-800">
                    <span className="truncate">{selectedVideo.name}</span>
                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() => setSelectedVideo(null)}
                      className="shrink-0 text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-50 dark:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>
            </section>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => router.back()}
                disabled={isLoading}
                className="rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}

                {isLoading ? "Creating..." : "Create Listing"}
              </button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}
