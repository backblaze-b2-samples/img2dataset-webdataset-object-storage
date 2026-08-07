import { describe, expect, it } from "vitest";

import { STATUS_CLASSNAMES, STATUS_VARIANTS } from "./corpus-status-badge";
import { badgeVariants } from "../ui/badge";
import { cn } from "../../lib/utils";

/**
 * `Badge` renders `cn(badgeVariants({ variant }), className)`, so this
 * reproduces that merge for each corpus status.
 *
 * The regression being guarded: "Complete" used to be a solid `--brand-b2` red
 * pill and "Failed" a solid `--destructive` red pill — two near-identical reds
 * separated only by their label text, so a corpora list gave no at-a-glance
 * signal that a bulk ingest had succeeded or failed.
 */
const merged = (status: keyof typeof STATUS_CLASSNAMES) =>
  cn(badgeVariants({ variant: STATUS_VARIANTS[status] }), STATUS_CLASSNAMES[status]);

// The badge base always carries `aria-invalid:*-destructive` styles, so the
// "not red" assertions target the fill/text utilities, not the substring.
const FILLED_RED = /\bbg-destructive\b|\bbg-\[var\(--brand-b2\)\]/;

describe("corpus status badge colours", () => {
  it("paints success with the success token, not a red", () => {
    const complete = merged("complete");
    expect(complete).toContain("bg-success-subtle");
    expect(complete).toContain("text-success");
    expect(complete).not.toContain("brand-b2");
    expect(complete).not.toMatch(FILLED_RED);
  });

  it("keeps failure on the destructive token", () => {
    const failed = merged("failed");
    expect(failed).toMatch(FILLED_RED);
    expect(failed).not.toContain("success");
  });

  it("gives the in-flight state its own treatment", () => {
    const running = merged("running");
    expect(running).toContain("bg-accent-subtle");
    expect(running).toContain("text-primary");
    expect(running).not.toContain("success");
    expect(running).not.toMatch(FILLED_RED);
  });

  it("gives every status a visually distinct class set", () => {
    const rendered = (["running", "complete", "failed"] as const).map(merged);
    expect(new Set(rendered).size).toBe(rendered.length);
  });
});
