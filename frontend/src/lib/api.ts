import { analysisSchema, type Analysis, type TripRequest } from "./contracts";
export class APIError extends Error {
  constructor(
    message: string,
    public code = "NETWORK_ERROR",
    public status?: number,
  ) {
    super(message);
  }
}
export async function analyzeTrip(
  request: TripRequest,
  signal: AbortSignal,
  timeoutMs = 120000,
): Promise<Analysis> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) controller.abort();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
    const response = await fetch(`${base}/api/routes/analyze/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new APIError(
        "The server returned an unreadable response. Try again shortly.",
        "INVALID_RESPONSE",
        response.status,
      );
    }
    if (!response.ok) {
      const envelope = data as {
        error?: { code?: string; message?: string; details?: unknown };
      };
      const code = envelope?.error?.code ?? "HTTP_ERROR";
      const messages: Record<string, string> = {
        PROVIDER_NOT_CONFIGURED:
          "Routing is temporarily unavailable. The server administrator needs to configure the provider.",
        LOCATION_AMBIGUOUS:
          "That location matches multiple places. Add a state and country, or use latitude, longitude.",
        LOCATION_UNRESOLVED:
          "A location could not be found. Try a full address or latitude, longitude.",
        NO_ROUTES: "No usable truck route was found. Try different endpoints.",
        PROVIDER_RATE_LIMIT:
          "The routing provider is busy. Wait a moment and retry.",
        PROVIDER_RESPONSE_INTERRUPTED:
          "The routing provider connection was interrupted. Please retry.",
        PROVIDER_TIMEOUT:
          "The routing provider did not respond in time. Please retry.",
      };
      // Never render arbitrary upstream bodies, HTML or exception text.
      throw new APIError(
        messages[code] ??
          (response.status === 400
            ? "Check the trip details, departure and coordinates, then retry."
            : "The analysis service is unavailable. Please retry shortly."),
        code,
        response.status,
      );
    }
    const parsed = analysisSchema.safeParse(data);
    if (!parsed.success)
      throw new APIError(
        "The server returned incomplete or invalid route data. Please retry.",
        "INVALID_RESPONSE",
      );
    return parsed.data;
  } catch (error) {
    if (timedOut)
      throw new APIError(
        "Analysis took too long. Try again or choose a shorter trip.",
        "TIMEOUT",
      );
    if (signal.aborted)
      throw new DOMException("Analysis cancelled", "AbortError");
    if (error instanceof APIError) throw error;
    throw new APIError(
      "Cannot reach the routing service. Check your connection and that the backend is running.",
    );
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}
