import { GoogleGenAI } from "@google/genai";
import { z } from "zod";

const requestSchema = z.object({
  description: z.string().trim().min(1).max(4000),
});

const extractedListingSchema = z.object({
  title: z.string().nullish(),
  description: z.string().nullish(),
  property_type: z.enum(["flat", "house_land"]).nullish(),
  price: z.number().finite().nullish(),
  bedrooms: z.number().finite().nullish(),
  bathrooms: z.number().finite().nullish(),
  floor_number: z.number().finite().nullish(),
  carpet_area: z.number().finite().nullish(),
  built_up_area: z.number().finite().nullish(),
  plot_area: z.number().finite().nullish(),
  lat: z.number().finite().nullish(),
  lng: z.number().finite().nullish(),
});

function toInputValue(value: number | string | null | undefined): string {
  return value === null || value === undefined ? "" : String(value).trim();
}

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "Request body must be valid JSON." },
      { status: 400 },
    );
  }

  const input = requestSchema.safeParse(body);

  if (!input.success) {
    return Response.json(
      { error: "Describe the property in 1 to 4000 characters." },
      { status: 400 },
    );
  }

  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    return Response.json(
      {
        error:
          "Listing AI is not configured. Set GEMINI_API_KEY on the server.",
      },
      { status: 503 },
    );
  }

  try {
    const ai = new GoogleGenAI({ apiKey });
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: [
        "Extract a real-estate listing from the broker's description. Return only a JSON object with exactly these keys: title, description, property_type, price, bedrooms, bathrooms, floor_number, carpet_area, built_up_area, plot_area, lat, lng.",
        'Use null for every detail not explicitly provided. Do not guess or add amenities, location coordinates, or property facts. Use "flat" for an explicitly stated apartment/flat and "house_land" for an explicitly stated house or land. Write a concise listing title and a polished description using only the provided facts. Return price as a plain number in INR, areas as plain numbers in square feet, and room counts, floor, latitude, and longitude as numbers.',
        "Broker's description:",
        input.data.description,
      ].join("\n\n"),
      config: {
        responseMimeType: "application/json",
      },
    });

    if (!response.text) {
      console.error(
        "Gemini returned an empty response for listing extraction.",
      );
      return Response.json(
        {
          error:
            "Gemini could not extract the property details. Please try again.",
        },
        { status: 502 },
      );
    }

    let extracted: unknown;

    try {
      extracted = JSON.parse(response.text);
    } catch (error) {
      console.error(
        "Gemini returned invalid JSON for listing extraction.",
        error,
      );
      return Response.json(
        { error: "Gemini returned an invalid response. Please try again." },
        { status: 502 },
      );
    }

    const parsed = extractedListingSchema.safeParse(extracted);

    if (!parsed.success) {
      console.error("Gemini returned invalid listing fields.", parsed.error);
      return Response.json(
        {
          error:
            "Gemini returned incomplete property details. Please try again.",
        },
        { status: 502 },
      );
    }

    const details = parsed.data;

    return Response.json({
      formData: {
        title: details.title?.trim() ?? "",
        description: details.description?.trim() ?? "",
        property_type: details.property_type ?? "",
        price: toInputValue(details.price),
        bedrooms: toInputValue(details.bedrooms),
        bathrooms: toInputValue(details.bathrooms),
        floor_number: toInputValue(details.floor_number),
        carpet_area: toInputValue(details.carpet_area),
        built_up_area: toInputValue(details.built_up_area),
        plot_area: toInputValue(details.plot_area),
        lat: toInputValue(details.lat),
        lng: toInputValue(details.lng),
      },
    });
  } catch (error) {
    console.error("Gemini listing extraction failed.", error);
    return Response.json(
      { error: "Unable to reach Gemini right now. Please try again." },
      { status: 502 },
    );
  }
}
