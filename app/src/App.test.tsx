import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import type { SceneDraft, WorkflowDraft } from "./types/draft";

const apiMocks = vi.hoisted(() => ({
  addScene: vi.fn(),
  apiAssetUrl: vi.fn((value: string) => value),
  fullUploadUrl: vi.fn((value: string) => value),
  confirmDraft: vi.fn(),
  createDraft: vi.fn(),
  createRun: vi.fn(),
  deleteScene: vi.fn(),
  getDraft: vi.fn(),
  getRenderLatest: vi.fn(),
  getRun: vi.fn(),
  listRuns: vi.fn(),
  listRunsPage: vi.fn(),
  listAvatarClones: vi.fn(),
  listTemplates: vi.fn(),
  listTemplateCategories: vi.fn(),
  uploadLocalFile: vi.fn(),
  outputUrl: vi.fn((value: string) => value),
  previewVoice: vi.fn(),
  previewCloneVoice: vi.fn(),
  reorderScenes: vi.fn(),
  rerenderRun: vi.fn(),
  copyDraftAsTemplate: vi.fn(),
  retryRun: vi.fn(),
  updateScene: vi.fn(),
  formatApiError: vi.fn((_error: unknown, fallback: string) => fallback),
}));

vi.mock("./api/drafts", () => ({ ...apiMocks }));
vi.mock("./components/editor/AvatarPicker", () => ({ AvatarPicker: () => null }));
vi.mock("./components/ui/Toast", () => ({ Toast: ({ message }: { message: string }) => message ? <div>{message}</div> : null }));

const template = {
  id: "intro_simple",
  name: "简洁开场",
  category: "intro",
  description: "主标题模板",
  builtin: true,
  enabled: true,
  fields: [{ key: "title", label: "主标题", required: true }],
};

function makeScene(over: Partial<SceneDraft> = {}): SceneDraft {
  return {
    id: "scene-1",
    position: 0,
    title: "开场",
    narration: "欢迎来到视频。",
    visual_intent: "渐变背景",
    subtitle: "",
    duration_seconds: 5,
    voice: "zh-CN-XiaoxiaoNeural",
    avatar: null,
    template_id: "intro_simple",
    template_fields: {},
    camera_motion: "zoom-in",
    media_width: 1280,
    media_height: 720,
    subtitle_display: "",
    subtitle_spoken: "",
    video_aspect: "16:9",
    video_transition_mode: "fade",
    ...over,
  };
}

function makeDraft(scene: SceneDraft): WorkflowDraft {
  return {
    id: "draft-app-test",
    title: "App 模板入口测试",
    source_script: "欢迎来到视频。",
    language: "zh-CN",
    status: "draft",
    version: 1,
    duration_seconds: 5,
    scenes: [scene],
    created_at: "2026-07-30T00:00:00Z",
    updated_at: "2026-07-30T00:00:00Z",
    confirmed_at: null,
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  localStorage.setItem("fliki-current-workflow-draft", "draft-app-test");
  apiMocks.listRuns.mockResolvedValue([]);
  apiMocks.listRunsPage.mockResolvedValue({ items: [], total: 0, page: 1, limit: 10, has_more: false });
  apiMocks.listAvatarClones.mockResolvedValue([]);
  apiMocks.listTemplates.mockResolvedValue([template]);
  apiMocks.listTemplateCategories.mockResolvedValue([{ category: "intro", count: 1 }]);
  apiMocks.getRun.mockResolvedValue(null);
  apiMocks.getDraft.mockResolvedValue(makeDraft(makeScene()));
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("App 全局模板补完入口 (D4-2)", () => {
  it("没有缺口时隐藏模板补完按钮", async () => {
    apiMocks.getDraft.mockResolvedValue(makeDraft(makeScene({ template_fields: { title: "已填标题" } })));
    render(<App />);
    await waitFor(() => expect(apiMocks.listTemplates).toHaveBeenCalled());
    expect(screen.queryByTestId("global-template-complete")).toBeNull();
  });

  it("有缺口时显示按钮，点击后展开 Composer 并聚焦首个场景", async () => {
    render(<App />);
    const button = await screen.findByTestId("global-template-complete");
    expect(button).toHaveTextContent("模板补完 (1)");
    expect(screen.queryByTestId("composer-coach-banner")).toBeNull();

    fireEvent.click(button);

    await screen.findByTestId("composer-coach-banner");
    const card = await screen.findByTestId("scene-meta-scene-1");
    await waitFor(() => {
      expect(card.className).toContain("sceneMetaCard-focus");
      expect(card.className).toContain("composerFocusPulse");
    });
    await waitFor(() => expect(apiMocks.listTemplates).toHaveBeenCalledTimes(1));
  });
});

describe('App Composer 失败回滚 (D5)', () => {
  it('PATCH 失败时回滚到 baseline 并显示 failed badge', async () => {
    apiMocks.updateScene.mockReset();
    apiMocks.updateScene.mockRejectedValue(new Error('PATCH 失败'));

    render(<App />);
    const button = await screen.findByTestId('global-template-complete');
    fireEvent.click(button);
    const fieldInput = await screen.findByTestId('template-field-scene-1-title');
    expect((fieldInput as HTMLInputElement).value).toBe('');

    fireEvent.change(fieldInput, { target: { value: 'rollback-target' } });
    await waitFor(() => {
      expect((screen.getByTestId('template-field-scene-1-title') as HTMLInputElement).value).toBe('rollback-target');
    });
    await waitFor(() => {
      expect(apiMocks.updateScene).toHaveBeenCalled();
    }, { timeout: 2000 });

    await waitFor(() => {
      const input = screen.getByTestId('template-field-scene-1-title') as HTMLInputElement;
      expect(input.value).toBe('');
    }, { timeout: 2000 });

    await waitFor(() => {
      expect(screen.getAllByText('保存失败').length).toBeGreaterThanOrEqual(1);
    }, { timeout: 2000 });
  });
});

describe('App runDraftAction 失败提示 (P0-2)', () => {
  it('"保存场景" 按钮 PATCH 失败时显示"操作失败"消息', async () => {
    apiMocks.updateScene.mockReset();
    apiMocks.updateScene.mockRejectedValue(new Error('PATCH 失败'));

    render(<App />);
    const saveButton = await screen.findByText(/保存场景/);
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiMocks.updateScene).toHaveBeenCalled();
    }, { timeout: 2000 });
    await waitFor(() => {
      expect(screen.getAllByText('操作失败').length).toBeGreaterThanOrEqual(1);
    }, { timeout: 2000 });
  });
});
describe('P2 草稿复制为模板', () => {
  it('点击"另存为模板"按钮后调用 copyDraftAsTemplate 并显示成功消息', async () => {
    apiMocks.copyDraftAsTemplate.mockReset();
    apiMocks.copyDraftAsTemplate.mockResolvedValue({
      id: 'copy_of_intro_simple',
      name: 'Copy of 简洁开场',
      category: 'intro',
      description: '顶部 logo 文字 + 居中主标题 + 副标题',
      builtin: false,
      enabled: true,
      created_at: 0,
      _source: { draft_id: 'draft-app-test', scene_id: 'scene-1', template_id: 'intro_simple' },
    } as any);

    render(<App />);
    // 展开 Composer
    const globalBtn = await screen.findByTestId('global-template-complete');
    fireEvent.click(globalBtn);
    // 找到"另存为模板"按钮
    const copyBtn = await screen.findByTestId('copy-as-template-scene-1');
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(apiMocks.copyDraftAsTemplate).toHaveBeenCalledTimes(1);
    });
    const callArgs = apiMocks.copyDraftAsTemplate.mock.calls[0];
    expect(callArgs[0]).toBe('draft-app-test');
    expect(callArgs[1]).toBe('scene-1');

    await waitFor(() => {
      expect(screen.getAllByText(/Copy of 简洁开场|模板已复制|已复制/).length).toBeGreaterThanOrEqual(1);
    }, { timeout: 2000 });
  });
});
