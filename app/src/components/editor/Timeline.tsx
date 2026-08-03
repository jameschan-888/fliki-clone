import { useState } from "react";
import { editorStore, editorActions, useEditorState } from "./editorStore";

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
      label: l.name + (l.visible ? "" : " (隐藏)"),
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
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.label}</span>
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
