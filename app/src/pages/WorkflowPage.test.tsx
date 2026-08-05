import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WorkflowPage } from "./WorkflowPage";

vi.mock("../components/layout/Footer", () => ({
  Footer: () => <footer data-testid="footer-stub" />,
}));

vi.mock("../api/auth", () => ({
  ensureSession: vi.fn().mockResolvedValue(undefined),
}));

beforeEach(() => {
  try { localStorage.clear(); } catch {}
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { href: "", reload: vi.fn() },
  });
  vi.clearAllMocks();
});

const DEFAULT_PROPS = {
  endpoint: "/workflow-drafts",
  title: "Script to Video",
  inputLabel: "脚本内容",
  inputField: "script",
  inputPlaceholder: "粘贴你的脚本...",
  mode: "text" as const,
};

function setupFetch(responder: (url: string, init: RequestInit) => Response) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    return Promise.resolve(responder(String(input), init || {}));
  });
}

describe("WorkflowPage R25 (rev41) - text mode", () => {
  it("renders h1 + form with htmlFor labels (a11y)", () => {
    render(<WorkflowPage {...DEFAULT_PROPS} />);
    expect(screen.getByRole("heading", { name: "Script to Video" })).toBeTruthy();
    expect(screen.getByLabelText("标题")).toBeTruthy();
    expect(screen.getByLabelText("语言")).toBeTruthy();
    expect(screen.getByLabelText("脚本内容")).toBeTruthy();
    expect(screen.getByRole("button", { name: /生成草稿/ })).toBeTruthy();
  });

  it("htmlFor id 关联正确 (input 有对应 id)", () => {
    const { container } = render(<WorkflowPage {...DEFAULT_PROPS} />);
    expect(container.querySelector("#wf-title")).toBeTruthy();
    expect(container.querySelector("#wf-language")).toBeTruthy();
    expect(container.querySelector("#wf-input")).toBeTruthy();
  });

  it("空 textarea 提交 -> 错误提示 (no network)", async () => {
    const spy = setupFetch(() => new Response("{}", { status: 200 }));
    const { container } = render(<WorkflowPage {...DEFAULT_PROPS} />);
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      const alert = container.querySelector("[role='alert']");
      expect(alert).toBeTruthy();
      expect(alert!.textContent).toContain("脚本内容 不能为空");
    });
    expect(spy.mock.calls.length).toBe(0);
  });

  it("valid submit -> POST endpoint + 成功块显示草稿 ID", async () => {
    setupFetch((url, init) => {
      if (init.method === "POST") return Promise.resolve(new Response(JSON.stringify({ id: "d-123", scenes: [{}, {}] }), { status: 200, headers: { "Content-Type": "application/json" } }));
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    const { container } = render(<WorkflowPage {...DEFAULT_PROPS} />);
    const textarea = screen.getByLabelText("脚本内容");
    fireEvent.change(textarea, { target: { value: "Hello world" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.textContent).toContain("d-123");
      expect(container.textContent).toContain("已生成 2 个 scene");
    });
  });

  it("submit 期间 aria-busy=true + button disabled", async () => {
    let resolvePost: ((v: Response) => void) | null = null;
    setupFetch((url, init) => {
      if (init.method === "POST") return new Promise<Response>((resolve) => { resolvePost = resolve; });
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    const { container } = render(<WorkflowPage {...DEFAULT_PROPS} />);
    const textarea = screen.getByLabelText("脚本内容");
    fireEvent.change(textarea, { target: { value: "Hi" } });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      const btn = container.querySelector("button[type=submit]") as HTMLButtonElement;
      expect(btn.getAttribute("aria-busy")).toBe("true");
      expect(btn.disabled).toBe(true);
      expect(btn.textContent).toBe("生成中...");
    });
    if (resolvePost) resolvePost(new Response(JSON.stringify({ id: "d-1", scenes: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
  });
});

describe("WorkflowPage R25 - translate mode", () => {
  const TRANSLATE_PROPS = {
    ...DEFAULT_PROPS,
    endpoint: "/workflow-translate",
    title: "Translate Video",
    inputLabel: "原文",
    inputField: "source",
    inputPlaceholder: "粘贴原文...",
    mode: "translate" as const,
  };

  it("render 源语言 + 目标语言 + 媒体文件 input (a11y)", () => {
    render(<WorkflowPage {...TRANSLATE_PROPS} />);
    expect(screen.getByLabelText("源语言")).toBeTruthy();
    expect(screen.getByLabelText("目标语言")).toBeTruthy();
    expect(screen.getByLabelText("媒体文件")).toBeTruthy();
    expect(screen.getByLabelText("原文")).toBeTruthy();
  });
});

describe("WorkflowPage R25 - record mode", () => {
  const RECORD_PROPS = {
    ...DEFAULT_PROPS,
    endpoint: "/workflow-record",
    title: "Record to Video",
    inputLabel: "转写文本",
    inputField: "transcript",
    inputPlaceholder: "录制后填入转写...",
    mode: "record" as const,
  };

  it("record 按钮有 aria-label 区分 开始/停止", () => {
    render(<WorkflowPage {...RECORD_PROPS} />);
    const recordBtn = screen.getByRole("button", { name: /开始录屏录音/ });
    expect(recordBtn.getAttribute("aria-label")).toBe("开始录屏录音");
  });
});
