import { z } from "zod";
export const locationSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  subtitle: z.string().optional(),
  source: z.string(),
  latitude: z.number().finite().min(-90).max(90),
  longitude: z.number().finite().min(-180).max(180),
});
export type SelectedLocation = z.infer<typeof locationSchema>;
export interface LocationFieldState {
  query: string;
  selected: SelectedLocation | null;
}
const suggestionSchema = z.object({
  id: z.string(),
  title: z.string(),
  subtitle: z.string(),
  type: z.string(),
  selectable: z.literal(true),
  reference: z.object({
    type: z.enum(["areas", "pois", "addresses", "streets", "intersections"]),
    id: z.string(),
  }),
});
export type Suggestion = z.infer<typeof suggestionSchema>;
const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
async function request(path: string, signal: AbortSignal, body?: unknown) {
  const response = await fetch(base + path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
    ...(body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
  });
  if (!response.ok)
    throw new Error(
      response.status === 503
        ? "Location search is busy or unavailable. Please retry."
        : "Location search failed. Please retry.",
    );
  return response.json();
}
export async function searchLocations(
  query: string,
  session: string,
  signal: AbortSignal,
): Promise<Suggestion[]> {
  return z
    .object({ suggestions: z.array(suggestionSchema).max(7) })
    .parse(
      await request(
        "/api/locations/suggest/?" +
          new URLSearchParams({ q: query, session_id: session }),
        signal,
      ),
    ).suggestions;
}
export async function resolveLocation(
  suggestion: Suggestion,
  session: string,
  signal: AbortSignal,
): Promise<SelectedLocation> {
  return locationSchema.parse(
    await request("/api/locations/resolve/", signal, {
      reference: suggestion.reference,
      session_id: session,
    }),
  );
}
export const exampleLocations: SelectedLocation[] = [
  {
    id: "example-chicago",
    label: "Chicago, Illinois, United States",
    source: "verified-example",
    latitude: 41.8781,
    longitude: -87.6298,
  },
  {
    id: "example-st-louis",
    label: "St. Louis, Missouri, United States",
    source: "verified-example",
    latitude: 38.627,
    longitude: -90.1994,
  },
];
export const fieldFor = (location: SelectedLocation): LocationFieldState => ({
  query: location.label,
  selected: location,
});
