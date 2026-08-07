import { describe, expect, it } from "vitest";

import { UPLOAD_PREFIX, isUrlListFile } from "./url-list-files";

describe("isUrlListFile", () => {
  it("accepts the URL-list formats img2dataset parses, under uploads/", () => {
    expect(isUrlListFile("uploads/custom-url-caption-list.tsv")).toBe(true);
    expect(isUrlListFile("uploads/list.csv")).toBe(true);
    expect(isUrlListFile("uploads/list.parquet")).toBe(true);
  });

  it("is case-insensitive about the extension", () => {
    expect(isUrlListFile("uploads/LIST.TSV")).toBe(true);
  });

  // The regression this guard exists for: img2dataset writes one metadata
  // parquet per shard into the app's own output prefix, so an extension-only
  // filter offered ~28 internal artifacts alongside the single real upload.
  it("rejects the app's own ingest output", () => {
    expect(
      isUrlListFile("img2dataset/8f3a1c/shards/00000.parquet")
    ).toBe(false);
    expect(isUrlListFile("img2dataset/8f3a1c/manifest.json")).toBe(false);
  });

  it("rejects uploads that img2dataset cannot parse as a URL list", () => {
    expect(isUrlListFile("uploads/photo.jpg")).toBe(false);
    expect(isUrlListFile("uploads/notes.txt")).toBe(false);
  });

  it("rejects a matching extension outside the upload prefix", () => {
    expect(isUrlListFile("list.tsv")).toBe(false);
    expect(isUrlListFile("other/uploads/list.tsv")).toBe(false);
  });

  it("exports the prefix the Upload page writes to", () => {
    expect(UPLOAD_PREFIX).toBe("uploads/");
  });
});
