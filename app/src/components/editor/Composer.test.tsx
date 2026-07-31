/**
rev24 阶段 D D2-3: Composer 模板引导测试.
覆盖:
  1. 模板卡片显示 fields 摘要 (必填 X · 可选 Y)
  2. 场景元数据卡片显示完成度 badge (incomplete 状态)
  3. 引导 banner 显示下一缺口
*/
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Composer } from "./Composer";
import type { SceneDraft } from "../../types/draft";
import type { TemplateMeta } from "../../api/drafts";

vi.stubEnv("VITE_API_BASE_URL", "http://test.local:9999");

function makeTemplate(over: Partial<TemplateMeta> = {}): TemplateMeta {
  return {
    id: "intro_simple",
    name: "简洁开场",
    category: "intro",
    description: "顶部 logo 文字 + 居中主标题 + 副标题",
    builtin: true,
    enabled: true,
    fields: [
      { key: "title", label: "主标题", required: true },
      { key: "subtitle", label: "副标题", required: false, default: "" },
      { key: "logo_text", label: "Logo 文字", required: false, default: "BRAND" },
    ],
    ...over,
  };
}

function makeScene(over: Partial<SceneDraft> = {}): SceneDraft {
  return {
    id: "scene-1",
    position: 0,
    title: "我的开场",
    narration: "欢迎来到...",
    visual_intent: "渐变背景",
    subtitle: "",
    duration_seconds: 5,
    voice: "zh-CN-XiaoxiaoNeural",
    avatar: null,
    template_id: null,
    template_fields: null,
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

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const s = String(url);
    if (s.endsWith("/templates/categories")) {
      return Promise.resolve(new Response(JSON.stringify([{ category: "intro", count: 1 }]), { status: 200 }));
    }
    if (s.includes("/templates?enabled_only=true&include_config=true")) {
      return Promise.resolve(new Response(JSON.stringify([makeTemplate()]), { status: 200 }));
    }
    return Promise.resolve(new Response("{}", { status: 200 }));
  });
});

const noop = () => undefined;

describe("Composer 模板引导 (rev24 D2-3)", () => {
  it("模板卡片显示 fields 摘要 (必填 1 · 可选 2)", async () => {
    const scene = makeScene();
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const summary = await screen.findByTestId("template-fields-intro_simple");
    expect(summary.textContent).toContain("必填 1");
    expect(summary.textContent).toContain("可选 2");
  });

  it("未选模板时不显示完成度 badge", async () => {
    const scene = makeScene();
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    await screen.findByTestId("template-card-intro_simple");
    expect(screen.queryByTestId("completion-scene-1")).toBeNull();
  });

  it("有 template_id 但 template_fields 为空 → 显示 incomplete badge", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: {} });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const badge = await screen.findByTestId("completion-scene-1");
    expect(badge.className).toContain("incomplete");
    expect(badge.textContent).toContain("0/1");
    expect(badge.textContent).toContain("主标题");
  });

  it("template_fields 全填 → 显示 complete badge", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: { title: "我的开场" } });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const badge = await screen.findByTestId("completion-scene-1");
    expect(badge.className).toContain("complete");
    expect(badge.textContent).toContain("1/1");
    expect(badge.textContent).toContain("✓");
  });

  it("有不完整场景时显示引导 banner", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: {} });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const banner = await screen.findByTestId("composer-coach-banner");
    expect(banner.textContent).toContain("下一缺口");
    expect(banner.textContent).toContain("主标题");
  });

  it("所有场景模板完整 → 不显示 banner", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: { title: "我的开场" } });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    await screen.findByTestId("template-card-intro_simple");
    expect(screen.queryByTestId("composer-coach-banner")).toBeNull();
  });

  it("点击 banner 跳到补完 → sceneMetaCard 加上 focus className", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: {} });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const banner = await screen.findByTestId("composer-coach-banner");
    const jumpBtn = screen.getByTestId("composer-coach-jump");
    fireEvent.click(jumpBtn);
    await waitFor(() => {
      const card = screen.getByTestId("scene-meta-scene-1");
      expect(card.className).toContain("sceneMetaCard-focus");
      // 顺便: banner 第一次跳过后, sceneMetaCard-incomplete 应保留
      expect(card.className).toContain("sceneMetaCard-incomplete");
    });
    expect(banner.textContent).toContain("下一缺口");
  });

  it("点击 banner 会调用目标 sceneMetaCard 的 scrollIntoView", async () => {
    const scene = makeScene({ template_id: "intro_simple", template_fields: {} });
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    const target = await screen.findByTestId("scene-meta-scene-1");
    const scrollIntoView = vi.fn();
    Object.assign(target, { scrollIntoView });
    fireEvent.click(screen.getByTestId("composer-coach-jump"));
    await waitFor(() => {
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    });
  });

  it("无 template_id 场景不出现在 banner / 不影响完成度", async () => {
    const a = makeScene({ id: "scene-a", template_id: null });
    const b = makeScene({ id: "scene-b", template_id: "intro_simple", template_fields: { title: "已填" } });
    render(<Composer scenes={[a, b]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={noop} onApplyTemplate={noop} />);
    await screen.findByTestId("template-card-intro_simple");
    expect(screen.queryByTestId("composer-coach-banner")).toBeNull();
    expect(screen.queryByTestId("completion-scene-a")).toBeNull();
    expect(screen.getByTestId("completion-scene-b").className).toContain("complete");
  });

  it("已选模板时显示文本字段，并合并回写 template_fields", async () => {
    const scene = makeScene({
      template_id: "intro_simple",
      template_fields: { title: "旧标题", subtitle: "保留副标题" },
    });
    const onUpdateScene = vi.fn();
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={onUpdateScene} onApplyTemplate={noop} />);

    const titleInput = await screen.findByTestId("template-field-scene-1-title");
    expect(titleInput.getAttribute("type")).toBe("text");
    fireEvent.change(titleInput, { target: { value: "新标题" } });

    expect(onUpdateScene).toHaveBeenCalledWith(scene, {
      template_fields: { title: "新标题", subtitle: "保留副标题" },
    });
  });

  it("number/select 字段按类型渲染并回写类型化值", async () => {
    const typedTemplate = makeTemplate({
      id: "typed_template",
      fields: [
        { key: "count", label: "数量", type: "number", required: true, min: 1, max: 10, step: 1 },
        { key: "tone", label: "语气", type: "select", required: true, options: ["正式", "轻松"] },
      ] as unknown as TemplateMeta["fields"],
    });
    vi.mocked(globalThis.fetch).mockImplementation((url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith("/templates/categories")) {
        return Promise.resolve(new Response(JSON.stringify([{ category: "intro", count: 1 }]), { status: 200 }));
      }
      if (requestUrl.includes("/templates?enabled_only=true&include_config=true")) {
        return Promise.resolve(new Response(JSON.stringify([typedTemplate]), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    const scene = makeScene({
      template_id: "typed_template",
      template_fields: { count: "2", tone: "正式" },
    });
    const onUpdateScene = vi.fn();
    render(<Composer scenes={[scene]} onReorder={noop} onPickTemplate={noop} onClearTemplate={noop} onUpdateScene={onUpdateScene} onApplyTemplate={noop} />);

    const numberInput = await screen.findByTestId("template-field-scene-1-count");
    const selectInput = screen.getByTestId("template-field-scene-1-tone");
    expect(numberInput.getAttribute("type")).toBe("number");
    expect(selectInput.tagName).toBe("SELECT");

    fireEvent.change(numberInput, { target: { value: "5" } });
    expect(onUpdateScene).toHaveBeenCalledWith(scene, {
      template_fields: { count: 5, tone: "正式" },
    });
    fireEvent.change(selectInput, { target: { value: "轻松" } });
    expect(onUpdateScene).toHaveBeenCalledWith(scene, {
      template_fields: { count: "2", tone: "轻松" },
    });
  });
});
