import { describe, expect, it } from "vitest";
import { geo, mmss, range, shortHash } from "./format";

describe("format", () => {
  it("formats seconds as mm:ss like the deck", () => {
    expect(mmss(42)).toBe("00:42");
    expect(mmss(68)).toBe("01:08");
    expect(mmss(600)).toBe("10:00");
    expect(mmss(null)).toBe("--:--");
  });
  it("formats the surfaced segment range with an en dash", () => {
    expect(range(42, 68)).toBe("00:42–01:08");
  });
  it("handles missing geotags and hashes", () => {
    expect(geo(null, null)).toBe("Location not captured");
    expect(geo(30.3165, 78.0322)).toBe("30.3165° N, 78.0322° E");
    expect(shortHash("abcdef0123456789", 6)).toBe("abcdef…");
  });
});
