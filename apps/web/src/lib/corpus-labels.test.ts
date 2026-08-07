import { describe, expect, it } from "vitest";

import {
  OUTPUT_FORMAT_LABELS,
  RESIZE_MODE_LABELS,
  outputFormatLabel,
  resizeModeLabel,
} from "./corpus-labels";
import {
  OUTPUT_FORMATS,
  RESIZE_MODES,
} from "@img2dataset-webdataset-object-storage/shared";

describe("corpus enum labels", () => {
  it("labels every value the API can store", () => {
    expect(Object.keys(OUTPUT_FORMAT_LABELS).sort()).toEqual(
      [...OUTPUT_FORMATS].sort(),
    );
    expect(Object.keys(RESIZE_MODE_LABELS).sort()).toEqual(
      [...RESIZE_MODES].sort(),
    );
  });

  it("never leaks a raw enum token to the screen", () => {
    for (const value of OUTPUT_FORMATS) {
      expect(outputFormatLabel(value)).not.toBe(value);
      expect(outputFormatLabel(value, "short")).not.toMatch(/_/);
    }
    for (const value of RESIZE_MODES) {
      expect(resizeModeLabel(value)).not.toBe(value);
      // "center_crop" used to render with its literal underscore.
      expect(resizeModeLabel(value)).not.toMatch(/_/);
      expect(resizeModeLabel(value, "short")).not.toMatch(/_/);
    }
  });

  it("renders the friendly forms the create dialog established", () => {
    expect(outputFormatLabel("webdataset")).toBe("WebDataset (.tar shards)");
    expect(outputFormatLabel("webdataset", "short")).toBe("WebDataset");
    expect(resizeModeLabel("no")).toBe("No resize");
    expect(resizeModeLabel("center_crop")).toBe("Center crop");
  });

  it("falls back to the raw value for an unknown token", () => {
    expect(outputFormatLabel("tfrecord")).toBe("tfrecord");
    expect(resizeModeLabel("something_new", "short")).toBe("something_new");
  });
});
