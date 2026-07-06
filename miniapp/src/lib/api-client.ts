import type {
  ApiErrorBody,
  ContinueWatchingItem,
  GenreResponse,
  SearchResponse,
  StreamTokenResponse,
} from "./types";
import { getInitData } from "./telegram";

// Same-origin by default (the backend can serve the Mini App bundle
// itself in dev, or a reverse proxy can put both behind one origin in
// prod) - override via VITE_API_BASE_URL for the CDN-hosted deployment
// described in README.md, where the Mini App and the API are on
// different origins.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // Telegram `initData` is the Mini App's whole authentication story -
  // see docs/architecture/auth.md. Sent as a Bearer token; the backend's
  // `AuthProvider` (once a real `telegram_init_data` adapter exists, see
  // that doc) is what actually verifies it - this client never
  // interprets or trusts it itself.
  const initData = getInitData();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (initData) {
    headers.set("Authorization", `Bearer ${initData}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body?.error) message = body.error;
    } catch {
      // Response body wasn't JSON - keep the generic message above.
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export function search(query: string, offset = 0, limit = 10): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    offset: String(offset),
    limit: String(limit),
  });
  return request<SearchResponse>(`/api/search?${params.toString()}`);
}

export function browseGenre(genre: string, offset = 0, limit = 20): Promise<GenreResponse> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return request<GenreResponse>(`/api/genres/${encodeURIComponent(genre)}?${params.toString()}`);
}

export function getContinueWatching(): Promise<{ items: ContinueWatchingItem[] }> {
  return request(`/api/continue-watching`);
}

export function recordWatchProgress(
  mediaId: string,
  positionSeconds: number,
  durationSeconds?: number
): Promise<{ status: string }> {
  return request(`/api/watch-progress`, {
    method: "POST",
    body: JSON.stringify({
      media_id: mediaId,
      position_seconds: Math.floor(positionSeconds),
      duration_seconds: durationSeconds ? Math.floor(durationSeconds) : undefined,
    }),
  });
}

export function getStreamToken(mediaId: string): Promise<StreamTokenResponse> {
  return request<StreamTokenResponse>(`/api/stream-token/${encodeURIComponent(mediaId)}`);
}

export function getDownloadToken(mediaId: string): Promise<StreamTokenResponse> {
  return request<StreamTokenResponse>(`/api/download-token/${encodeURIComponent(mediaId)}`);
}

// A fixed, client-side genre list for the Browse page's grid - see
// genre_browsing/plugin.py's docstring for why `GET /api/genres` (list
// all distinct names) isn't implemented yet; this is the workaround it
// names explicitly ("a client that already knows genre names ... can
// call the per-genre route directly").
export const BROWSE_GENRES = [
  "Action",
  "Adventure",
  "Animation",
  "Comedy",
  "Crime",
  "Documentary",
  "Drama",
  "Fantasy",
  "Horror",
  "Romance",
  "Sci-Fi",
  "Thriller",
] as const;
