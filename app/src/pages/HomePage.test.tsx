import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { HomePage } from "./HomePage";

// Mock child components that pull network / DOM APIs not relevant to HomePage logic.
vi.mock("../App", () => ({
  default: () => <div data-testid="app-stub" />,
}));
vi.mock("../components/layout/EnvCheckBadge", () => ({
  EnvCheckBadge: () => <span data-testid="env-check-stub" />,
}));
vi.mock("../components/layout/Footer", () => ({
  Footer: () => <footer data-testid="footer-stub" />,
}));
vi.mock("../components/editor/ProviderKeyManager", () => ({
  ProviderKeyManager: () => <div data-testid="pkm-stub" />,
}));

let _href = "";
beforeEach(() => {
  _href = "";
  try { localStorage.clear(); } catch {}
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      get href() { return _href; },
      set href(v: string) { _href = String(v); (window as any).__lastHref = String(v); },
      reload: vi.fn(),
    },
  });
  (window as any).__lastHref = "";
  vi.clearAllMocks();
});

function mockJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetchSequence(responses: Array<(url: string, init: RequestInit) => Response>) {
  let call = 0;
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    const responder = responses[Math.min(call, responses.length - 1)];
    call++;
    return Promise.resolve(responder(url, init || {}));
  });
}

function makeFile(name: string, type = "image/png"): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type });
}

describe("HomePage R13 (rev39)", () => {
  it("renders nav, App stub, Footer stub", () => {
    render(<HomePage />);
    expect(screen.getByTestId("app-stub")).toBeTruthy();
    expect(screen.getByTestId("footer-stub")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Avatar 库/ })).toBeTruthy();
  });

  it("opening Avatar modal exposes form with htmlFor-labeled inputs (a11y)", async () => {
    mockFetchSequence([(url) => mockJsonResponse([])]);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Avatar 库/ }));
    await waitFor(() => {
      expect(screen.getByLabelText("Avatar 名称")).toBeTruthy();
      expect(screen.getByLabelText("人脸图片")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: /保存/ })).toBeTruthy();
  });

  it("empty submit -> 需要名称和人脸图片 (no fetch POST)", async () => {
    const fetchSpy = mockFetchSequence([(url) => mockJsonResponse([])]);
    const { container } = render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Avatar 库/ }));
    await waitFor(() => screen.getByLabelText("Avatar 名称"));
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".error")?.textContent).toBe("需要名称和人脸图片");
    });
    const postCalls = fetchSpy.mock.calls.filter(([, init]) => init && (init as RequestInit).method === "POST");
    expect(postCalls.length).toBe(0);
  });

  it("valid submit -> POST /avatar-clones with avatar_name + ref_face (FormData)", async () => {
    const fetchSpy = mockFetchSequence([
      // 0: GET on modal open -> []
      () => mockJsonResponse([]),
      // 1: POST create -> { avatar_name: "MyClone" }
      () => mockJsonResponse({ avatar_name: "MyClone" }, 201),
      // 2: GET refresh after create -> [new avatar]
      () => mockJsonResponse([{ uuid: "u1", avatar_name: "MyClone", ref_face_path: "x.png", enabled: true }]),
    ]);
    const { container } = render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Avatar 库/ }));
    const nameInput = await screen.findByLabelText("Avatar 名称");
    fireEvent.change(nameInput, { target: { value: "MyClone" } });
    const fileInput = screen.getByLabelText("人脸图片") as HTMLInputElement;
    const file = makeFile("face.png");
    Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
    fireEvent.change(fileInput);
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".hint.ok")?.textContent).toContain("已创建 MyClone");
    });
    const postCall = fetchSpy.mock.calls.find(([, init]) => init && (init as RequestInit).method === "POST");
    expect(postCall).toBeTruthy();
    const fd = (postCall![1] as RequestInit).body as FormData;
    expect(fd).toBeInstanceOf(FormData);
    expect(fd.get("avatar_name")).toBe("MyClone");
    expect(fd.get("language")).toBe("zh");
    expect(fd.get("ref_face")).toBeInstanceOf(File);
  });

  it("POST error -> .error shows server message", async () => {
    mockFetchSequence([
      (url) => mockJsonResponse([]),
      () => mockJsonResponse({ message: "上传失败" }, 500),
    ]);
    const { container } = render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Avatar 库/ }));
    const nameInput = await screen.findByLabelText("Avatar 名称");
    fireEvent.change(nameInput, { target: { value: "BadName" } });
    const fileInput = screen.getByLabelText("人脸图片") as HTMLInputElement;
    Object.defineProperty(fileInput, "files", { value: [makeFile("face.png")], configurable: true });
    fireEvent.change(fileInput);
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => {
      expect(container.querySelector(".error")?.textContent).toContain("上传失败");
    });
  });

  it("close button (✕) hides modal", async () => {
    mockFetchSequence([(url) => mockJsonResponse([])]);
    const { container } = render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: /Avatar 库/ }));
    await waitFor(() => screen.getByLabelText("Avatar 名称"));
    const closeBtn = container.querySelector(".modalHeader button") as HTMLButtonElement;
    fireEvent.click(closeBtn);
    await waitFor(() => {
      expect(screen.queryByLabelText("Avatar 名称")).toBeNull();
    });
  });
});
