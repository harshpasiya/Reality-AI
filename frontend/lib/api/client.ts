import { useAuthStore } from "@/stores/authStore";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/** An HTTP error from the backend, with its status code kept for callers. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return (
    error instanceof ApiError &&
    (status === undefined || error.status === status)
  );
}

/** A message that is safe to show to the user for any thrown value. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError) {
    // fetch() throws TypeError when the server can't be reached at all.
    return "Can't reach the server. Check that the backend is running and try again.";
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{loc: [...], msg: "..."}, ...]
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const { loc, msg } = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined;
        const text = (msg ?? "").replace(/^Value error, /, "");
        return field && field !== "body" ? `${String(field)}: ${text}` : text;
      })
      .filter(Boolean)
      .join("; ");
  }
  return "";
}

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
        message =
          detailToText(errorBody.detail) ||
          detailToText(errorBody.message) ||
          detailToText(errorBody.error);
      }
    } catch {
      message = responseText;
    }
  }

  const safeMessage = message.trim().slice(0, 500);
  return safeMessage || `Request failed (${response.status})`;
}

/** Sign out and send the user to the login page, coming back here after. */
function handleExpiredSession() {
  useAuthStore.getState().logout();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    const back = window.location.pathname + window.location.search;
    // Called outside React (no router here), so a full navigation is intended.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?redirect=${encodeURIComponent(back)}`);
  }
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
    if (response.status === 401 && token) {
      handleExpiredSession();
      throw new ApiError(401, "Your session has expired. Please log in again.");
    }
    throw new ApiError(
      response.status,
      await getResponseErrorMessage(response),
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Turn a backend media path such as "/uploads/3/a.jpg" into a full URL. */
export function mediaUrl(path: string | null | undefined): string | undefined {
  const value = path?.trim();
  if (!value) return undefined;
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_URL}${value.startsWith("/") ? "" : "/"}${value}`;
}
