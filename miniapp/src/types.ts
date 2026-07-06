// Mirrors docs/api/reference.md response shapes. Kept as one small file
// (not generated from the Python models) since the API surface is small
// enough that hand-keeping these in sync is lower overhead than a
// codegen step for this phase - see README.md if that trade-off changes.

export interface SearchVariant {
  media_id: string;
  language: string;
  quality: string;
  codec: string;
  release_type: string;
  file_size: number;
}

export interface SearchResultGroup {
  title: string;
  year: number | null;
  variant_count: number;
  languages: string[];
  qualities: string[];
  variants: SearchVariant[];
}

export interface SearchResponse {
  results: SearchResultGroup[];
  total: number;
  has_more: boolean;
}

export interface GenreListItem {
  media_id: string;
  title: string;
  year: number | null;
}

export interface GenreResponse {
  genre: string;
  items: GenreListItem[];
}

export interface ContinueWatchingItem {
  media_id: string;
  position_seconds: number;
  duration_seconds: number;
}

export interface StreamTokenResponse {
  url: string;
  expires_at: string;
  file_name: string;
  file_size: number;
  mime_type: string;
}

export interface ApiErrorBody {
  error: string;
}
