import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AutoEditPage } from "./AutoEditPage";

// mock API base URL via Vite env var
vi.stubEnv("VITE_API_BASE_URL", "http://test.local:9999");

beforeEach(() => {
  // 健康检查 mock
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const s = String(url);
    if (s.endsWith("/health")) {
      return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    }
    return Promise.resolve(new Response("{}", { status: 200 }));
  });
});

describe("AutoEditPage smoke (rev24 阶段 C P1-B)", () => {
  it("renders header and upload panel", async () => {
    const { container } = render(<AutoEditPage />);
    expect(screen.getByText(/Auto-edit 视频剪辑/)).toBeInTheDocument();
    // ApiStatus 异步更新
    await waitFor(() => {
      expect(screen.getByText(/API: ok|API: 连接失败|API: --/)).toBeInTheDocument();
    });
    // file input 存在
    expect(container.querySelector('input[type="file"]')).toBeTruthy();
    // 上传卡片标题在
    expect(screen.getByText(/① 上传视频/)).toBeInTheDocument();
  });

  it("hides draft panel before upload", () => {
    render(<AutoEditPage />);
    expect(screen.queryByText(/② 草稿/)).toBeNull();
  });

  it("hides run panel before generation", () => {
    render(<AutoEditPage />);
    expect(screen.queryByText(/③ 生成进度/)).toBeNull();
  });
});

const warnMocks = vi.hoisted(() => ({
  uploadVideoXhr: vi.fn(),
  createDraftFromUpload: vi.fn(),
}));
vi.mock("../api/autoedit", async () => {
  const actual = await vi.importActual<typeof import("../api/autoedit")>("../api/autoedit");
  return { ...actual, uploadVideoXhr: warnMocks.uploadVideoXhr, createDraftFromUpload: warnMocks.createDraftFromUpload };
});

describe("AutoEditPage 转写警告 banner (P1 item 2)", () => {
  beforeEach(() => {
    warnMocks.uploadVideoXhr.mockReset();
    warnMocks.createDraftFromUpload.mockReset();
  });
  it("draft 返 transcription_warning 时显示 banner 含原文警告文本", async () => {
    const fakeUpload = {
      id: "u1", filename: "test.mp4", size_bytes: 1000,
      duration_seconds: 30, width: 1920, height: 1080, container: "mp4",
    };
    const fakeDraft = {
      id: "draft-warn",
      upload_id: "u1",
      title: "测试草稿",
      status: "draft",
      version: 1,
      language: "zh-CN",
      duration_seconds: 12.5,
      upload: fakeUpload,
      segments: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      confirmed_at: null,
      transcription_warning: "本地转写需要 faster-whisper; 请 pip install faster-whisper",
      transcription_source: "unavailable",
    };
    warnMocks.uploadVideoXhr.mockResolvedValue(fakeUpload);
    warnMocks.createDraftFromUpload.mockResolvedValue(fakeDraft);
    const { fireEvent } = await import("@testing-library/react");
    const file = new File(["x"], "test.mp4", { type: "video/mp4" });
    const { container } = render(<AutoEditPage />);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });
    const draftBtn = await screen.findByText(/生成可编辑草稿/, undefined, { timeout: 3000 });
    fireEvent.click(draftBtn);
    await waitFor(() => expect(screen.getByTestId("autoedit-transcription-warning")).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByTestId("autoedit-transcription-warning")).toHaveTextContent("faster-whisper");
  });
});

describe("ToastContainer auto-hide (rev24 阶段 C P1-B)", () => {
  it("renders nothing when no toasts", async () => {
    const { ToastContainer } = await import("../components/ui/ToastContainer");
    const { container } = render(<ToastContainer toasts={[]} onDismiss={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
