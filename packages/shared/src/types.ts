export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  /** Set when a format-specific extractor was skipped or failed (e.g. an image
   *  above the decompression-bomb decode limit). Core fields stay exact. */
  metadata_warning: string | null;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

/** A short-lived presigned PUT the browser uploads a file directly to B2 with.
 *  `headers` are signed into the URL, so the browser must send them verbatim. */
export interface PresignUploadResponse {
  key: string;
  url: string;
  method: string;
  content_type: string;
  headers: Record<string, string>;
  expires_in: number;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Corpus (primary entity: an img2dataset ingest job) --------------------

export type OutputFormat = "webdataset" | "parquet" | "files";
export type ResizeMode = "border" | "keep_ratio" | "center_crop" | "no";
export type ImageSize = 256 | 384 | 512;
export type UrlListSource = "seed" | "uploaded";
export type CorpusStatus = "running" | "complete" | "failed";

export const OUTPUT_FORMATS: OutputFormat[] = ["webdataset", "parquet", "files"];
export const RESIZE_MODES: ResizeMode[] = [
  "border",
  "keep_ratio",
  "center_crop",
  "no",
];
export const IMAGE_SIZES: ImageSize[] = [256, 384, 512];

export interface ShardStat {
  name: string;
  count: number;
  successes: number;
  failed_to_download: number;
  failed_to_resize: number;
  tar_key: string | null;
  bytes: number;
  size_human: string;
}

export interface CorpusMetrics {
  image_count: number;
  successes: number;
  failed: number;
  yield_pct: number;
  shard_count: number;
  total_bytes: number;
  total_bytes_human: string;
  duration_seconds: number;
}

export interface Corpus {
  id: string;
  name: string;
  description: string;
  output_format: OutputFormat;
  resize_mode: ResizeMode;
  image_size: ImageSize;
  url_list_source: UrlListSource;
  bucket_key: string | null;
  status: CorpusStatus;
  prefix: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  metrics: CorpusMetrics;
  shards: ShardStat[];
}

/** POST /corpora body. */
export interface CorpusCreate {
  name: string;
  description?: string;
  output_format: OutputFormat;
  resize_mode: ResizeMode;
  image_size: ImageSize;
  url_list_source: UrlListSource;
  bucket_key?: string | null;
}

/** PATCH /corpora/{id} body — only name/description are mutable. */
export interface CorpusUpdate {
  name?: string;
  description?: string;
}

export interface PreviewSample {
  key: string;
  caption: string;
  thumbnail: string;
  width: number;
  height: number;
}

export interface CorpusPreview {
  corpus_id: string;
  shard_key: string | null;
  samples: PreviewSample[];
  note: string | null;
}

export interface CorpusStats {
  total_corpora: number;
  running: number;
  complete: number;
  failed: number;
  images_ingested: number;
  shards_written: number;
  aggregate_yield_pct: number;
  total_bytes: number;
  total_bytes_human: string;
}
