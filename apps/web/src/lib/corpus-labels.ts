import type {
  OutputFormat,
  ResizeMode,
} from "@img2dataset-webdataset-object-storage/shared";

/**
 * The single source of truth for the plain-English names of the corpus enums.
 *
 * These values are stored as internal tokens (`center_crop`, `no`,
 * `webdataset`) and must never reach the screen raw. Every surface that shows
 * one — the create dialog's selectors, the detail page's Configuration card,
 * the corpora-list card — reads its label from here, so a corpus reads the same
 * way everywhere.
 *
 * `label` is the full form for a selector or a definition list; `short` is the
 * compact form for a dense one-line summary.
 */
export interface EnumLabel {
  label: string;
  short: string;
}

export const OUTPUT_FORMAT_LABELS: Record<OutputFormat, EnumLabel> = {
  webdataset: { label: "WebDataset (.tar shards)", short: "WebDataset" },
  parquet: { label: "Parquet (images embedded)", short: "Parquet" },
  files: { label: "Files (one object per image)", short: "Files" },
};

export const RESIZE_MODE_LABELS: Record<ResizeMode, EnumLabel> = {
  border: { label: "Border (pad to square)", short: "Border" },
  keep_ratio: { label: "Keep ratio", short: "Keep ratio" },
  center_crop: { label: "Center crop", short: "Center crop" },
  no: { label: "No resize", short: "No resize" },
};

/**
 * Falls back to the raw token for a value the maps don't know: a manifest
 * written by a newer version should degrade to "unlabelled", never to a blank.
 */
function labelFor<T extends string>(
  labels: Record<T, EnumLabel>,
  value: string,
  variant: keyof EnumLabel,
): string {
  return labels[value as T]?.[variant] ?? value;
}

export function outputFormatLabel(
  value: string,
  variant: keyof EnumLabel = "label",
): string {
  return labelFor(OUTPUT_FORMAT_LABELS, value, variant);
}

export function resizeModeLabel(
  value: string,
  variant: keyof EnumLabel = "label",
): string {
  return labelFor(RESIZE_MODE_LABELS, value, variant);
}
