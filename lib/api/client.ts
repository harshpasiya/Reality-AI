import { useAuthStore } from "@/stores/authStore";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getResponseErrorMessage(
  response: Response,
): Promise<string> {
  const responseText = await response.text();
  let message = "";

  if (responseText) {
    try {
      const body: unknown = JSON.parse(responseText);
      if (typeof body === "string") {
        message = body;
      } else if (body && typeof body === "object") {
        const errorBody = body as Record<string, unknown>;
        const detail =
          errorBody.message ??
          errorBody.detail ??
          errorBody.error_description ??
          errorBody.error;
        if (typeof detail === "string") {
          message = detail;
        }
      }
    } catch {
      message = responseText;
    }
  }

  const status = `${response.status} ${response.statusText}`.trim();
  const safeMessage = message.trim().slice(0, 500);
  return safeMessage ? `${status}: ${safeMessage}` : status;
}

export async function apiClient<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = useAuthStore.getState().accessToken;

  const headers = new Headers(options.headers);

  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = endpoint.startsWith("/api/") ? endpoint : `${API_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(await getResponseErrorMessage(response));
  }

  return response.json() as Promise<T>;
}
