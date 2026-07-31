import { describe, it, expect } from "vitest";
import { outputUrl, formatApiError } from "./autoedit";

describe("outputUrl (rev24 阶段 C P1-B)", () => {
  it("returns null for null/undefined/empty", () => {
    expect(outputUrl(null)).toBeNull();
    expect(outputUrl(undefined)).toBeNull();
    expect(outputUrl("")).toBeNull();
  });

  it("encodes basename and prefixes /outputs/", () => {
    const url = outputUrl("rendered/clip.mp4");
    expect(url).toContain("/outputs/");
    expect(url).toContain("clip.mp4");
    expect(url).not.toContain("rendered/");
  });

  it("handles flat filenames", () => {
    const url = outputUrl("foo.mp4");
    expect(url).toMatch(/\/outputs\/foo\.mp4$/);
  });

  it("preserves basename even with windows path separators", () => {
    const url = outputUrl("C:\\renders\\clip.mp4");
    expect(url).toContain("clip.mp4");
    expect(url).not.toContain("C:");
  });
});

describe("formatApiError re-export from drafts", () => {
  it("delegates to drafts.formatApiError", () => {
    expect(formatApiError(null, "x")).toBe("x");
    expect(formatApiError("oops", "x")).toBe("oops");
    expect(formatApiError({ status: 500, message: "no", hint: "", details: {} }, "x")).toBe("no");
  });
});
