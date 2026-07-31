import { useEffect, useState } from "react";

// D2-3: 模板完成度计算
type TemplateFieldOption = string | { value: string; label?: string };
type TemplateField = {
  key: string;
  label?: string;
  type?: "text" | "number" | "select";
  required?: boolean;
  default?: string | number;
  placeholder?: string;
  max_length?: number;
  min?: number;
  max?: number;
  step?: number;
  options?: TemplateFieldOption[];
};
export type TemplateCompletion = {
  templateId: string | null;
  templateName: string | null;
  required: number;
  filled: number;
  missing: string[];
  isComplete: boolean;
};

export function computeTemplateCompletion(
  scene: SceneDraft,
  templateLookup: Map<string, TemplateMeta>,
): TemplateCompletion {
  if (!scene.template_id) {
    return { templateId: null, templateName: null, required: 0, filled: 0, missing: [], isComplete: true };
  }
  const tpl = templateLookup.get(scene.template_id);
  if (!tpl) {
    return { templateId: scene.template_id, templateName: scene.template_id, required: 0, filled: 0, missing: [], isComplete: true };
  }
  const fields = (tpl.fields || []) as Array<TemplateField>;
  const required = fields.filter((f) => f.required);
  const filledUserFields = scene.template_fields || {};
  const missing: string[] = [];
  let filled = 0;
  for (const f of required) {
    const v = filledUserFields[f.key];
    const hasValue = v != null && String(v).trim() !== "";
    const hasDefault = f.default != null && String(f.default).trim() !== "";
    if (hasValue || hasDefault) {
      filled += 1;
    } else {
      missing.push(f.label || f.key);
    }
  }
  return {
    templateId: scene.template_id,
    templateName: tpl.name,
    required: required.length,
    filled,
    missing,
    isComplete: missing.length === 0,
  };
}

function summarizeTemplateFields(tpl: TemplateMeta | null): string {
  if (!tpl) return "无字段";
  const fields = (tpl.fields || []) as Array<TemplateField>;
  const required = fields.filter((f) => f.required).length;
  const optional = fields.length - required;
  if (required === 0 && optional === 0) return "无字段";
  return "必填 " + required + " · 可选 " + optional;
}

export function findNextIncompleteScene(scenes: SceneDraft[], lookup: Map<string, TemplateMeta>): { sceneId: string; missing: string[] } | null {
  for (const scene of scenes) {
    const c = computeTemplateCompletion(scene, lookup);
    if (scene.template_id && !c.isComplete) {
      return { sceneId: scene.id, missing: c.missing };
    }
  }
  return null;
}

import type { TemplateMeta } from "../../api/drafts";
import { getTemplateCatalogSnapshot, loadTemplateCatalogWithRetry, subscribeTemplateCache } from "../../api/templateCache";
import type { SceneDraft } from "../../types/draft";

type SaveStatus = "idle" | "saving" | "saved" | "failed";
type Props = {
  scenes: SceneDraft[];
  onReorder: (fromIndex: number, toIndex: number) => void;
  onPickTemplate: (scene: SceneDraft) => void;
  onClearTemplate: (scene: SceneDraft) => void;
  onCopyAsTemplate?: (scene: SceneDraft) => void;
  onUpdateScene: (scene: SceneDraft, patch: Partial<SceneDraft>) => void;
  onApplyTemplate: (scene: SceneDraft, template: TemplateMeta) => void;
  saveStatusByScene?: Record<string, SaveStatus>;
  disabled?: boolean;
  // D2-3: 模板引导 (可选 external focus; 不传则内部跳转)
  focusSceneId?: string | null;
};

const SAVE_STATUS_LABEL: Record<SaveStatus, string> = {
  idle: "",
  saving: "保存中…",
  saved: "已保存",
  failed: "保存失败",
};

const MEDIA_PRESETS: Array<{ label: string; width: number; height: number }> = [
  { label: "16:9 横屏", width: 1280, height: 720 },
  { label: "9:16 竖屏", width: 720, height: 1280 },
  { label: "1:1 方形", width: 720, height: 720 },
];

const ASPECT_OPTIONS: Array<{ value: "16:9" | "9:16" | "1:1"; label: string }> = [
  { value: "16:9", label: "16:9 横屏" },
  { value: "9:16", label: "9:16 竖屏" },
  { value: "1:1", label: "1:1 方形" },
];

const TRANSITION_OPTIONS: Array<{ value: "none" | "fade" | "cut" | "slide-left" | "slide-right" | "slide-up" | "slide-down"; label: string }> = [
  { value: "none", label: "无" },
  { value: "fade", label: "渐入渐出 (默认推荐)" },
  { value: "cut", label: "硬切" },
  { value: "slide-left", label: "左滑" },
  { value: "slide-right", label: "右滑" },
  { value: "slide-up", label: "上滑" },
  { value: "slide-down", label: "下滑" },
];

export function Composer({ scenes, onReorder, onPickTemplate, onClearTemplate, onCopyAsTemplate, onUpdateScene, onApplyTemplate, saveStatusByScene, disabled, focusSceneId }: Props) {
  const [templates, setTemplates] = useState<TemplateMeta[]>(() => getTemplateCatalogSnapshot().templates);
  const [categories, setCategories] = useState(() => getTemplateCatalogSnapshot().categories);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [targetSceneId, setTargetSceneId] = useState<string>(() => scenes[0]?.id || "");
  const [templateState, setTemplateState] = useState<"loading" | "ready" | "error">(() => {
    const status = getTemplateCatalogSnapshot().status;
    return status === "idle" ? "loading" : status;
  });
  const templateLookup = new Map<string, TemplateMeta>(templates.map((t) => [t.id, t]));
  // D2-3: internal 焦点 — banner 跳转 push, 滚动 effect 消费
  const [focusSceneIdLocal, setFocusSceneIdLocal] = useState<string | null>(null);
  const [focusPulseSceneId, setFocusPulseSceneId] = useState<string | null>(null);
  const effectiveFocusSceneId = focusSceneId ?? focusSceneIdLocal;

  useEffect(() => {
    const snapshot = getTemplateCatalogSnapshot();
    setTemplates(snapshot.templates);
    setCategories(snapshot.categories);
    setTemplateState(snapshot.status === "idle" ? "loading" : snapshot.status);
    const unsubscribe = subscribeTemplateCache((nextSnapshot) => {
      setTemplates(nextSnapshot.templates);
      setCategories(nextSnapshot.categories);
      setTemplateState(nextSnapshot.status === "idle" ? "loading" : nextSnapshot.status);
    });
    const cachedTemplateIds = new Set(snapshot.templates.map((template) => template.id));
    const referencesMissingTemplate = scenes.some((scene) => scene.template_id && !cachedTemplateIds.has(scene.template_id));
    if (snapshot.status === "idle" || snapshot.status === "error" || referencesMissingTemplate) {
      loadTemplateCatalogWithRetry();
    }
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!scenes.some((scene) => scene.id === targetSceneId)) {
      setTargetSceneId(scenes[0]?.id || "");
    }
  }, [scenes, targetSceneId]);

  // D2-3: 收到 focusSceneId, 滚动到对应 sceneMetaCard + 短暂高亮
  useEffect(() => {
    if (!effectiveFocusSceneId) return;
    const el = document.querySelector(`[data-scene-meta-id="${effectiveFocusSceneId}"]`);
    if (el) {
      if (typeof el.scrollIntoView === "function") el.scrollIntoView({ behavior: "smooth", block: "center" });
      setFocusPulseSceneId(effectiveFocusSceneId);
      const t = setTimeout(() => setFocusPulseSceneId(null), 1500);
      return () => clearTimeout(t);
    }
  }, [effectiveFocusSceneId]);


  const targetScene = scenes.find((scene) => scene.id === targetSceneId) || scenes[0];

  const filteredTemplates = activeCategory
    ? templates.filter((t) => t.category === activeCategory)
    : templates;

  function handleTemplateFieldChange(scene: SceneDraft, field: TemplateField, rawValue: string) {
    const nextValue = field.type === "number" && rawValue !== "" ? Number(rawValue) : rawValue;
    onUpdateScene(scene, {
      template_fields: {
        ...(scene.template_fields || {}),
        [field.key]: nextValue,
      },
    });
  }

  function handleDragStart(index: number) {
    if (disabled) return;
    setDraggingIndex(index);
  }
  function handleDragOver(e: React.DragEvent, index: number) {
    if (disabled || draggingIndex === null) return;
    e.preventDefault();
  }
  function handleDrop(index: number) {
    if (disabled || draggingIndex === null || draggingIndex === index) {
      setDraggingIndex(null);
      return;
    }
    onReorder(draggingIndex, index);
    setDraggingIndex(null);
  }

  return (
    <div className="composer">
      {/* D2-3: 模板引导 banner */}
      {(() => {
        const next = findNextIncompleteScene(scenes, templateLookup);
        if (!next) return null;
        const targetScene = scenes.find((s) => s.id === next.sceneId);
        return (
          <div className="composerCoachBanner" data-testid="composer-coach-banner" role="status">
            <span className="composerCoachBannerIcon">📋</span>
            <span className="composerCoachBannerText">
              下一缺口: <strong>{targetScene?.title || "场景"}</strong> 模板补完还差 <strong>{next.missing.join(", ")}</strong>
            </span>
            <button type="button" className="composerCoachBannerBtn" data-testid="composer-coach-jump" onClick={() => setFocusSceneIdLocal(next.sceneId)}>
                跳到补完 →
              </button>
          </div>
        );
      })()}
      {/* 模板库面板 (P0-2) */}
      <div className="composerHeader">
        <div className="composerHeaderTitle">🧩 模板库 <span className={"composerSaveBadge " + (saveStatusByScene?.[targetSceneId] || "idle")}>{SAVE_STATUS_LABEL[saveStatusByScene?.[targetSceneId] || "idle"]}</span></div>
        <select
          className="composerCategorySelect"
          value={activeCategory}
          onChange={(e) => setActiveCategory(e.target.value)}
          disabled={disabled}
        >
          <option value="">全部分类 ({templates.length})</option>
          {categories.map((c) => (
            <option key={c.category} value={c.category}>
              {c.category} ({c.count})
            </option>
          ))}
        </select>
        <select
          className="composerCategorySelect"
          value={targetScene?.id || ""}
          onChange={(event) => setTargetSceneId(event.target.value)}
          disabled={disabled || scenes.length === 0}
          aria-label="模板目标场景"
        >
          {scenes.map((scene, index) => (
            <option key={scene.id} value={scene.id}>
              套用到场景 {index + 1}: {scene.title}
            </option>
          ))}
        </select>
      </div>
      <div className="templateRail">
        {templateState === "loading" ? (
          <div className="templateRailEmpty">正在加载真实模板目录…</div>
        ) : templateState === "error" ? (
          <div className="templateRailEmpty error">模板接口不可用；时间轴和场景编辑仍可继续</div>
        ) : filteredTemplates.length === 0 ? (
          <div className="templateRailEmpty">当前分类没有可用模板</div>
        ) : (
          filteredTemplates.map((template) => (
            <button
              type="button"
              key={template.id}
              className={"templateCard " + (targetScene?.template_id === template.id ? "selected" : "")}
              title={template.description}
              disabled={disabled || !targetScene}
              onClick={() => targetScene && onApplyTemplate(targetScene, template)}
              data-testid={"template-card-" + template.id}
            >
              <div className="templateCardName">{template.name}</div>
              <div className="templateCardDescription">{template.description}</div>
              <div className="templateCardFieldsSummary" data-testid={"template-fields-" + template.id}>{summarizeTemplateFields(template)}</div>
              <div className="templateCardMeta">
                <span className="templateTag">{template.category}</span>
                {template.builtin && <span className="templateTag builtin">内置</span>}
                {targetScene?.template_id === template.id && <span className="templateTag selected">已套用</span>}
              </div>
            </button>
          ))
        )}
      </div>

      {/* 时间轴 (P0-2 拖拽时间线) */}
      <div className="composerHeader" style={{ marginTop: 20 }}>
        <div className="composerHeaderTitle">⏱ 时间轴 ({scenes.length} 场景)</div>
        <div className="composerHint">拖拽场景卡片可重排顺序, 已确认草稿禁止编辑</div>
      </div>
      <ol className="timelineList">
        {scenes.map((scene, index) => {
          const duration = Number(scene.duration_seconds) || 2;
          const width = Math.max(80, duration * 24);
          return (
            <li
              key={scene.id}
              className={`timelineItem ${draggingIndex === index ? "dragging" : ""}`}
              draggable={!disabled}
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDrop={() => handleDrop(index)}
            >
              <div className="timelineIndex">{index + 1}</div>
              <div className="timelineBar" style={{ width }}>
                <div className="timelineTitle">{scene.title}</div>
                <div className="timelineDuration">{duration.toFixed(1)}s</div>
              </div>
              <div className="timelineMeta">
                <span className="templateTag">{scene.template_id ? "模板 ✓" : "无模板"}</span>
                <span className="templateTag">
                  {scene.media_width}×{scene.media_height}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      {/* 模板元数据 + 双轨字幕 + media 宽高 (P0-2 + P0-4 + P0-5) */}
      <div className="composerHeader" style={{ marginTop: 24 }}>
        <div className="composerHeaderTitle">📝 场景元数据</div>
        <div className="composerHint">subtitle_display = 屏幕显示 / subtitle_spoken = TTS 朗读</div>
      </div>
      <div className="sceneMetaList">
        {scenes.map((scene) => {
          const completion = computeTemplateCompletion(scene, templateLookup);
          const activeTemplate = completion.templateId ? templateLookup.get(completion.templateId) : null;
          const templateFields = (activeTemplate?.fields || []) as TemplateField[];
          return (
          <div key={scene.id} className={"sceneMetaCard " + (completion.templateId && !completion.isComplete ? "sceneMetaCard-incomplete " : "") + (effectiveFocusSceneId === scene.id ? "sceneMetaCard-focus " : "") + (focusPulseSceneId === scene.id ? "composerFocusPulse" : "")} data-scene-meta-id={scene.id} data-testid={"scene-meta-" + scene.id}>
            <div className="sceneMetaTitle">
              <span>{scene.title}</span>
              {completion.templateId && (
                <span className={"sceneMetaCompletionBadge " + (completion.isComplete ? "complete" : "incomplete")} data-testid={"completion-" + scene.id}>
                  模板 {completion.templateName} · {completion.filled}/{completion.required}
                  {completion.isComplete ? " ✓" : " ⚠️ 缺: " + completion.missing.join(", ")}
                </span>
              )}
            </div>
            <div className="sceneMetaGrid">
              <label>
                <span>subtitle_display</span>
                <textarea
                  rows={2}
                  value={scene.subtitle_display || ""}
                  disabled={disabled}
                  onChange={(e) => onUpdateScene(scene, { subtitle_display: e.target.value })}
                />
              </label>
              <label>
                <span>subtitle_spoken (TTS)</span>
                <textarea
                  rows={2}
                  value={scene.subtitle_spoken || ""}
                  disabled={disabled}
                  onChange={(e) => onUpdateScene(scene, { subtitle_spoken: e.target.value })}
                />
              </label>
              <label>
                <span>media 宽高</span>
                <select
                  disabled={disabled}
                  value={`${scene.media_width || 1280}x${scene.media_height || 720}`}
                  onChange={(e) => {
                    const [w, h] = e.target.value.split("x").map(Number);
                    onUpdateScene(scene, { media_width: w, media_height: h });
                  }}
                >
                  {MEDIA_PRESETS.map((p) => (
                    <option key={`${p.width}x${p.height}`} value={`${p.width}x${p.height}`}>
                      {p.label} ({p.width}×{p.height})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>video_aspect (Pixelle)</span>
                <select
                  disabled={disabled}
                  value={scene.video_aspect || "16:9"}
                  onChange={(e) => onUpdateScene(scene, { video_aspect: e.target.value as "16:9" | "9:16" | "1:1" })}
                >
                  {ASPECT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>video_transition_mode (Pixelle)</span>
                <select
                  disabled={disabled}
                  value={scene.video_transition_mode || "fade"}
                  onChange={(e) => onUpdateScene(scene, { video_transition_mode: e.target.value as "none" | "fade" | "cut" | "slide-left" | "slide-right" | "slide-up" | "slide-down" })}
                >
                  {TRANSITION_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <div className="sceneMetaTemplateRow">
                <span className="sceneMetaTemplateLabel">模板: {scene.template_id || "未选"}</span>
                <div className="sceneMetaTemplateActions">
                  <button type="button" disabled={disabled} onClick={() => onPickTemplate(scene)}>
                    选择模板
                  </button>
                  {scene.template_id && (
                    <button type="button" disabled={disabled} onClick={() => onClearTemplate(scene)}>
                      清除
                    </button>
                  )}
                  {scene.template_id && (
                    <button
                      type="button"
                      disabled={disabled}
                      data-testid={"copy-as-template-" + scene.id}
                      onClick={() => onCopyAsTemplate?.(scene)}
                    >
                      另存为模板
                    </button>
                  )}
                </div>
              </div>
              {scene.template_id && activeTemplate && templateFields.length > 0 && (
                <div className="sceneTemplateFields" data-testid={"template-fields-form-" + scene.id}>
                  <div className="sceneTemplateFieldsHeader">
                    <strong>{activeTemplate.name} 字段</strong>
                    <span>修改后自动保存</span>
                  </div>
                  <div className="sceneTemplateFieldsGrid">
                    {templateFields.map((field) => {
                      const storedValue = scene.template_fields?.[field.key];
                      const fieldValue = storedValue ?? field.default ?? "";
                      const fieldLabel = (field.label || field.key) + (field.required ? " *" : "");
                      if (field.type === "select") {
                        return (
                          <label key={field.key}>
                            <span>{fieldLabel}</span>
                            <select
                              value={String(fieldValue)}
                              disabled={disabled}
                              required={field.required}
                              data-testid={"template-field-" + scene.id + "-" + field.key}
                              onChange={(event) => handleTemplateFieldChange(scene, field, event.target.value)}
                            >
                              {fieldValue === "" && <option value="">请选择</option>}
                              {(field.options || []).map((option) => {
                                const optionValue = typeof option === "string" ? option : option.value;
                                const optionLabel = typeof option === "string" ? option : (option.label || option.value);
                                return <option key={optionValue} value={optionValue}>{optionLabel}</option>;
                              })}
                            </select>
                          </label>
                        );
                      }
                      if (field.type === "number") {
                        return (
                          <label key={field.key}>
                            <span>{fieldLabel}</span>
                            <input
                              type="number"
                              value={fieldValue}
                              min={field.min}
                              max={field.max}
                              step={field.step}
                              placeholder={field.placeholder}
                              disabled={disabled}
                              required={field.required}
                              data-testid={"template-field-" + scene.id + "-" + field.key}
                              onChange={(event) => handleTemplateFieldChange(scene, field, event.target.value)}
                            />
                          </label>
                        );
                      }
                      return (
                        <label key={field.key}>
                          <span>{fieldLabel}</span>
                          <input
                            type="text"
                            value={String(fieldValue)}
                            maxLength={field.max_length}
                            placeholder={field.placeholder}
                            disabled={disabled}
                            required={field.required}
                            data-testid={"template-field-" + scene.id + "-" + field.key}
                            onChange={(event) => handleTemplateFieldChange(scene, field, event.target.value)}
                          />
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
