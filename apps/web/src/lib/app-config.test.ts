import { describe, expect, it } from "vitest";
import { APP_DESCRIPTION, APP_NAME } from "@/lib/app-config";

describe("app identity", () => {
  it("ships the canonical app name and description", () => {
    expect(APP_NAME).toBe("img2dataset → WebDataset on B2");
    expect(APP_DESCRIPTION).toBe(
      "Bulk-download image-text datasets into Backblaze B2 as reproducible WebDataset shards with img2dataset."
    );
  });
});
