import { useState } from "react";
import { MediaPanel, type MediaPanelProps } from "./panels/MediaPanel";
import { AudioPanel, type AudioPanelProps } from "./panels/AudioPanel";
import { SubtitlesPanel, type SubtitlesPanelProps } from "./panels/SubtitlesPanel";
import { TemplatesPanel, type TemplatesPanelProps } from "./panels/TemplatesPanel";
import { SettingsPanel, type SettingsPanelProps } from "./panels/SettingsPanel";
import { BrandKitPanel, type BrandKitPanelProps } from "./panels/BrandKitPanel";
import { CopilotPanel, CharacterPanel, ElementsPanel, RecordPanel, LayersPanel } from "./panels/AdvancedPanels";
const TOOLS = [
  { id: "media", label: "Media", icon: "🖼️" }, { id: "audio", label: "Audio", icon: "🎙️" },
  { id: "subtitles", label: "Subtitles", icon: "💬" }, { id: "templates", label: "Templates", icon: "🧩" },
  { id: "settings", label: "Settings", icon: "⚙️" }, { id: "brandkit", label: "Brand", icon: "🎨" },
  { id: "copilot", label: "Copilot", icon: "✨" }, { id: "character", label: "Character", icon: "🧑" },
  { id: "elements", label: "Elements", icon: "🔷" }, { id: "record", label: "Record", icon: "⏺️" }, { id: "layers", label: "Layers", icon: "▤" },
];
type ToolId = typeof TOOLS[number]["id"];
export type EditorSidebarProps = { media?: MediaPanelProps; audio?: AudioPanelProps; subtitles?: SubtitlesPanelProps; templates?: TemplatesPanelProps; settings?: SettingsPanelProps; brandkit?: BrandKitPanelProps };
export function EditorSidebar(props: EditorSidebarProps) {
  const [active, setActive] = useState<ToolId | null>("media");
  return <div className="sidebar"><div className="sidebarTools" role="tablist">{TOOLS.map((tool) => <button key={tool.id} className={"sidebarTool" + (active === tool.id ? " active" : "")} onClick={() => setActive(active === tool.id ? null : tool.id)} title={tool.label} role="tab" aria-selected={active === tool.id}><span className="sidebarIcon">{tool.icon}</span><span className="sidebarLabel">{tool.label}</span></button>)}</div>{active && <div className="sidebarContent">
    {active === "media" && <MediaPanel onPick={props.media?.onPick} />}
    {active === "audio" && <AudioPanel onPick={props.audio?.onPick} />}
    {active === "subtitles" && <SubtitlesPanel onPick={props.subtitles?.onPick} activeId={props.subtitles?.activeId} />}
    {active === "templates" && <TemplatesPanel onPick={props.templates?.onPick} />}
    {active === "settings" && <SettingsPanel onChange={props.settings?.onChange} initial={props.settings?.initial} />}
    {active === "brandkit" && <BrandKitPanel onChange={props.brandkit?.onChange} initial={props.brandkit?.initial} />}
    {active === "copilot" && <CopilotPanel />}
    {active === "character" && <CharacterPanel />}
    {active === "elements" && <ElementsPanel />}
    {active === "record" && <RecordPanel />}
    {active === "layers" && <LayersPanel />}
  </div>}</div>;
}
export default EditorSidebar;
