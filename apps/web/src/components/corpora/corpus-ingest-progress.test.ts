import { describe, expect, it } from "vitest";

import { formatElapsed } from "./corpus-ingest-progress";

describe("formatElapsed", () => {
  it("stays in seconds under a minute", () => {
    expect(formatElapsed(0)).toBe("0s");
    expect(formatElapsed(18.4)).toBe("18s");
    expect(formatElapsed(59.4)).toBe("59s");
  });

  it("switches to minutes and zero-pads the seconds", () => {
    expect(formatElapsed(60)).toBe("1m 00s");
    expect(formatElapsed(185)).toBe("3m 05s");
  });

  it("never shows negative time from a clock skew", () => {
    expect(formatElapsed(-3)).toBe("0s");
  });
});
