import { describe, it, expect } from "vitest";
import { formatApiError, type ApiError } from "../api/drafts";

describe("formatApiError (rev15)", () => {
  it("returns fallback when given empty input", () => {
    expect(formatApiError(null, "操作失败")).toBe("操作失败");
    expect(formatApiError(undefined, "操作失败")).toBe("操作失败");
  });

  it("returns the string when given a string", () => {
    expect(formatApiError("自定义错误", "操作失败")).toBe("自定义错误");
  });

  it("formats ApiError with message only", () => {
    const e: ApiError = { status: 500, message: "服务器开小差", hint: "", details: {} };
    expect(formatApiError(e, "操作失败")).toBe("服务器开小差");
  });

  it("appends hint in parentheses when present", () => {
    const e: ApiError = { status: 409, message: "草稿未确认", hint: "请先点确认草稿", details: {} };
    expect(formatApiError(e, "操作失败")).toBe("草稿未确认（请先点确认草稿）");
  });

  it("falls back when ApiError has no message", () => {
    const e: ApiError = { status: 400, message: "", hint: "", details: {} };
    expect(formatApiError(e, "操作失败")).toBe("操作失败");
  });

  it("handles Error instance", () => {
    expect(formatApiError(new Error("boom"), "操作失败")).toBe("boom");
  });
});
