import { useState } from "react";
import { MediaPanel, type MediaPanelProps } from "./panels/MediaPanel";
import { AudioPanel, type AudioPanelProps } from "./panels/AudioPanel";
import { SubtitlesPanel, type SubtitlesPanelProps } from "./panels/SubtitlesPanel";
import { TemplatesPanel, type TemplatesPanelProps } from "./panels/TemplatesPanel";
import { SettingsPanel, type SettingsPanelProps } from "./panels/SettingsPanel";
import { BrandKitPanel, type BrandKitPanelProps } from "./panels/BrandKitPanel";

const TOOLS = [
  { id: "media", label: "Media", icon: "🖼️" },
  { id: "audio", label: "Audio", icon: "🎙️" },
  { id: "subtitles", label: "Subtitles", icon: "💬" },
  { id: "templates", label: "Templates", icon: "🧩" },
  { id: "settings", label: "Settings", icon: "⚙️" },
  { id: "brandkit", label: "Brand", icon: "🎨" },
];

type ToolId = typeof TOOLS[number]["id"];

export type EditorSidebarProps = {
  media?: MediaPanelProps;
  audio?: AudioPanelProps;
  subtitles?: SubtitlesPanelProps;
  templates?: TemplatesPanelProps;
  settings?: SettingsPanelProps;
  brandkit?: BrandKitPanelProps;
};

export function EditorSidebar(props: EditorSidebarProps) {
  var _a = useState<ToolId | null>("media"), active = _a[0], setActive = _a[1];
  return (
    <div className="sidebar">
      <div className="sidebarTools" role="tablist">
        {TOOLS.map(function (t) { return (
          <button
            key={t.id}
            className={"sidebarTool" + (active === t.id ? " active" : "")}
            onClick={function () { setActive(active === t.id ? null : t.id); }}
            title={t.label}
            role="tab"
            aria-selected={active === t.id}
          >
            <span className="sidebarIcon">{t.icon}</span>
            <span className="sidebarLabel">{t.label}</span>
          </button>
        ); })}
      </div>
      {active && (
        <div className="sidebarContent">
          {active === "media" && <MediaPanel onPick={props.media?.onPick} />}
          {active === "audio" && <AudioPanel onPick={props.audio?.onPick} />}
          {active === "subtitles" && <SubtitlesPanel onPick={props.subtitles?.onPick} activeId={props.subtitles?.activeId} />}
          {active === "templates" && <TemplatesPanel onPick={props.templates?.onPick} />}
          {active === "settings" && <SettingsPanel onChange={props.settings?.onChange} initial={props.settings?.initial} />}          {active === "brandkit" && <BrandKitPanel onChange={props.brandkit?.onChange} initial={props.brandkit?.initial} />}
          {active === "brandkit" && <BrandKitPanel onChange={props.brandkit?.onChange} initial={props.brandkit?.initial} />}
        </div>
      )}
    </div>
  );
}

export default EditorSidebar;
