import { useState } from "react";
// P3.3: Timeline element/layer thumbnail mapping. 来自 app/public/fliki-assets/.
// element.id 形如 "watermark-abc123", 取前缀 kind 匹配.
const THUMB_BY_KIND: Record<string, string> = {
  // elements (16 种 from ELEMENT_TYPES in AdvancedPanels.tsx)
  shape: "/fliki-assets/videos/info.webp",
  sticker: "/fliki-assets/videos/training.webp",
  icon: "/fliki-assets/videos/review.webp",
  bar: "/fliki-assets/videos/ad.webp",
  arrow: "/fliki-assets/videos/promo.webp",
  cta: "/fliki-assets/videos/promo.webp",
  highlight: "/fliki-assets/testimonials/maya.webp",
  line: "/fliki-assets/testimonials/rachel.webp",
  "lower-third": "/fliki-assets/testimonials/james.webp",
  bubble: "/fliki-assets/videos/educational.webp",
  counter: "/fliki-assets/videos/explainer.webp",
  "background-blur": "/fliki-assets/series/creators.webp",
  lottie: "/fliki-assets/videos/ad.webp",
  caption: "/fliki-assets/videos/tutorial.webp",
  logo: "/fliki-assets/testimonials/rachel.webp",
  watermark: "/fliki-assets/series/ep1.webp",
  // layers
  background: "/fliki-assets/series/creators.webp",
  video: "/fliki-assets/videos/promo.webp",
  avatar: "/fliki-assets/testimonials/maya.webp",
  element: "/fliki-assets/videos/info.webp",
  subtitle: "/fliki-assets/videos/tutorial.webp",
};

function thumbFor(id: string): string | null {
  if (!id) return null;
  if (THUMB_BY_KIND[id]) return THUMB_BY_KIND[id];
  const prefix = id.split("-")[0];
  return THUMB_BY_KIND[prefix] || null;
}

import { editorStore, editorActions, useEditorState } from "./editorStore";
import { LayerOpacityBar } from "./LayerOpacityBar";

export type TimelineScene = {
  id: string;
  index: number;
  duration_seconds: number;
  subtitle?: string;
  voice?: string;
  visual?: string;
};

type Clip = {
  id: string;
  label: string;
  duration_seconds: number;
  scene_index?: number;
  kind?: string;
  opacity?: number;
  locked?: boolean;
  character_id?: string;
};

type Track = {
  id: string;
  label: string;
  kind: string;
  clips: Clip[];
  isSync?: boolean;
  source?: string;
};

export type TimelineProps = {
  scenes: TimelineScene[];
  audio_clips?: Array<{ id: string; label: string; duration_seconds: number }>;
  music_clips?: Array<{ id: string; label: string; duration_seconds: number }>;
  transcript_clips?: Array<{ id: string; label: string; duration_seconds: number; scene_index: number }>;
  onSelectScene?: (id: string) => void;
  onAddScene?: () => void;
  onPlayStateChange?: (playing: boolean) => void;
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m.toString().padStart(2, "0") + ":" + s.toString().padStart(2, "0");
}

export function Timeline(props: TimelineProps) {
  const scenes = props.scenes || [];
  const audioClips = props.audio_clips || [];
  const musicClips = props.music_clips || [];
  const transcriptClips = props.transcript_clips || [];
  const totalDuration = scenes.reduce((s: number, sc: TimelineScene) => s + (sc.duration_seconds || 0), 0);

  const layers = useEditorState((s: any) => s.layers);
  const elements = useEditorState((s: any) => s.elements);
  const character = useEditorState((s: any) => s.character);
  const selectedSceneFromStore = useEditorState((s: any) => s.selected_scene_id);
  const storePlaying = useEditorState((s: any) => s.playing);
  const playhead = useEditorState((s: any) => s.playhead);

  const [localPlaying, setLocalPlaying] = useState<boolean>(false);
  const [zoom, setZoom] = useState<number>(1);
  const [view, setView] = useState<"basic" | "timeline">("timeline");
  const playing = storePlaying || localPlaying;

  function togglePlay(): void {
    const next = !playing;
    setLocalPlaying(next);
    editorActions.togglePlay();
    if (props.onPlayStateChange) props.onPlayStateChange(next);
  }

  function reset(): void {
    editorActions.setPlayhead(0);
    setLocalPlaying(false);
  }
  function zoomIn(): void { setZoom(Math.min(3, zoom + 0.25)); }
  function zoomOut(): void { setZoom(Math.max(0.5, zoom - 0.25)); }

  function clickScene(id: string): void {
    editorActions.setSelectedScene(id);
    if (props.onSelectScene) props.onSelectScene(id);
  }

  const sceneTrack: Track = {
    id: "scene",
    label: "Scene",
    kind: "scene",
    clips: scenes.map((s: TimelineScene) => ({
      id: s.id,
      label: "S" + (s.index + 1),
      duration_seconds: s.duration_seconds,
      scene_index: s.index,
    })),
  };

  const audioTrack: Track = {
    id: "audio",
    label: "Audio",
    kind: "audio",
    clips: audioClips.map((a) => ({
      id: a.id,
      label: a.label,
      duration_seconds: a.duration_seconds,
    })),
  };

  const musicTrack: Track = {
    id: "music",
    label: "Music",
    kind: "music",
    clips: musicClips.map((m) => ({
      id: m.id,
      label: m.label,
      duration_seconds: m.duration_seconds,
    })),
  };

  const transcriptTrack: Track = {
    id: "transcript",
    label: "字幕",
    kind: "transcript",
    clips: transcriptClips.map((t) => ({
      id: t.id,
      label: t.label,
      duration_seconds: t.duration_seconds,
      scene_index: t.scene_index,
    })),
  };

  const layerTrack: Track = {
    id: "layers",
    label: "Layers",
    kind: "layer",
    isSync: true,
    source: "Layers panel",
    clips: layers.map((l: any) => ({
      id: l.id,
      label: l.name + " · " + l.opacity + "%" + (l.visible ? "" : " (隐藏)") + (l.locked ? " [lock]" : ""),
      duration_seconds: totalDuration,
      kind: l.kind,
      opacity: l.opacity,
      locked: l.locked,
    })),
  };

  const elementTrack: Track = {
    id: "elements",
    label: "Elements",
    kind: "element",
    isSync: true,
    source: "Elements panel",
    clips: elements.map((e: any, i: number) => ({
      id: e.id,
      label: e.position + " · " + e.size + "% · " + e.opacity + "% · " + e.width + "x" + e.height + "@(" + e.x + "," + e.y + ")",
      duration_seconds: totalDuration / Math.max(1, elements.length),
      kind: "element",
      opacity: e.opacity,
      scene_index: i,
    })),
  };

  const avatarTrack: Track | null = character ? {
    id: "avatar",
    label: "Avatar",
    kind: "avatar",
    isSync: true,
    source: "Character panel",
    clips: [{
      id: "char-" + character.id,
      label: character.name + " · " + character.style + " · " + character.region,
      duration_seconds: totalDuration,
      character_id: character.id,
    }],
  } : null;

  const tracks: Track[] = [sceneTrack, layerTrack, elementTrack]
    .concat(avatarTrack ? [avatarTrack] : [])
    .concat([transcriptTrack, audioTrack, musicTrack]);

  function renderClip(c: Clip, kind: string) {
    const w = Math.max(40, (c.duration_seconds || 1) * 60 * zoom);
    const opacity = c.opacity != null ? c.opacity / 100 : 1;
    const thumbnailUrl = c.id ? thumbFor(c.id) : null;
    const isLayerClip = kind === "layer";
    const layerKey = (c.kind && (editorStore.kindColor as any)[c.kind]) ? c.kind : null;
    const bgLayer = layerKey ? (editorStore.kindColor as any)[layerKey] : "#5b6cff";
    const bgEl = c.character_id ? "#f5a524" : (c.kind === "element" ? "#19b5c5" : bgLayer);

    return (
      <div
        key={c.id}
        className={"tl-clip " + kind + (c.locked ? " locked" : "")}
        style={{ width: w + "px", opacity: opacity, background: bgEl + "55", borderColor: bgEl }}
        onClick={() => { if (c.id) clickScene(c.id); }}
        title={c.label + " · " + (c.duration_seconds || 0) + "s" + (c.opacity != null ? " · " + c.opacity + "%" : "")}
      >
        {kind === "scene" && <span className="idx">{(c.scene_index || 0) + 1}</span>}
        {isLayerClip && (
          <LayerOpacityBar
            layerId={c.id}
            opacity={c.opacity ?? 100}
            fillColor={((editorStore.kindColor as any)[c.kind as string] as string) || "#5b6cff"}
            onChange={(opacity) => editorActions.setLayerOpacity(c.id, opacity)}
          />
        )}
        {thumbnailUrl && (
          <img
            src={thumbnailUrl}
            alt=""
            data-testid="timeline-thumb"
            style={{
              width: 32,
              height: 18,
              objectFit: "cover",
              borderRadius: 2,
              marginRight: 6,
              flexShrink: 0,
              border: "1px solid rgba(255,255,255,0.15)",
            }}
          />
        )}
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{c.label}</span>
        <span className="dur">{c.duration_seconds ? c.duration_seconds.toFixed(1) + "s" : ""}</span>
      </div>
    );
  }

  return (
    <section className="tl">
      <div className="tl-head">
        <button className="tl-play" onClick={togglePlay}>{playing ? "⏸ Pause" : "▶ Play"}</button>
        <div className="tl-time">{formatTime(playhead)} / {formatTime(totalDuration)}</div>
        <div className="tl-zoom">
          <button onClick={zoomOut}>−</button>
          <span className="lvl">{Math.round(zoom * 100)}%</span>
          <button onClick={zoomIn}>+</button>
          <button onClick={reset}>Reset</button>
        </div>
        <div className="tl-tabs">
          <button className={view === "basic" ? "active" : ""} onClick={() => setView("basic")}>Basic</button>
          <button className={view === "timeline" ? "active" : ""} onClick={() => setView("timeline")}>Timeline</button>
        </div>
      </div>

      <div className="tl-tracks">
        {tracks.map((tr) => (
          <div key={tr.id} className={"tl-track" + (tr.isSync ? " tl-sync" : "")}>
            <div className="tl-track-label">
              {tr.label}
              <small>{tr.clips.length} clip{tr.isSync ? " · ⇄ " + tr.source : ""}</small>
            </div>
            <div className="tl-strip">
              {tr.clips.length === 0 ? (
                <span className="tl-empty">空轨道{tr.isSync ? " · 来自 " + tr.source : ""}</span>
              ) : tr.clips.map((c) => renderClip(c, tr.kind))}
            </div>
          </div>
        ))}
      </div>

      {(selectedSceneFromStore || layers.length > 0 || elements.length > 0 || character) ? (
        <div className="tl-status">
          store: {selectedSceneFromStore ? "scene=" + selectedSceneFromStore + " " : ""}
          {layers.length} layers · {elements.length} elements · character={character ? character.name : "—"}
        </div>
      ) : null}
    </section>
  );
}

export default Timeline;
