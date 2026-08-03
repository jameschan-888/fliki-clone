import { useState } from "react";

export type TimelineScene = {
  id: string;
  index: number;
  duration_seconds: number;
  subtitle?: string;
  voice?: string;
  visual?: string;
};

export type TimelineTrack = {
  id: string;
  label: string;
  kind: "scene" | "audio" | "music" | "transcript";
  clips: Array<{ id: string; label: string; duration_seconds: number; scene_index?: number }>;
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
  var m = Math.floor(seconds / 60);
  var s = Math.floor(seconds % 60);
  return m.toString().padStart(2, "0") + ":" + s.toString().padStart(2, "0");
}

export function Timeline(props: TimelineProps) {
  var scenes = props.scenes || [];
  var audioClips = props.audio_clips || [];
  var musicClips = props.music_clips || [];
  var transcriptClips = props.transcript_clips || [];
  var totalDuration = scenes.reduce(function (s, sc) { return s + (sc.duration_seconds || 0); }, 0);
  var voiceCount = new Set(scenes.map(function (s) { return s.voice || ""; }).filter(Boolean)).size;

  var _a = useState(false), playing = _a[0], setPlaying = _a[1];
  var _b = useState(0), playhead = _b[0], setPlayhead = _b[1];
  var _c = useState(1), zoom = _c[0], setZoom = _c[1];
  var _d = useState("timeline"), view = _d[0], setView = _d[1];
  var _e = useState<string | null>(null), selectedScene = _e[0], setSelectedScene = _e[1];

  function togglePlay() {
    var next = !playing;
    setPlaying(next);
    if (props.onPlayStateChange) props.onPlayStateChange(next);
  }

  function reset() { setPlayhead(0); setPlaying(false); }
  function zoomIn() { setZoom(Math.min(3, zoom + 0.25)); }
  function zoomOut() { setZoom(Math.max(0.5, zoom - 0.25)); }

  function clickScene(id: string) {
    setSelectedScene(id);
    if (props.onSelectScene) props.onSelectScene(id);
  }

  var sceneTrack: TimelineTrack = {
    id: "scene",
    label: "Scene",
    kind: "scene",
    clips: scenes.map(function (s) { return { id: s.id, label: "S" + s.index, duration_seconds: s.duration_seconds, scene_index: s.index }; }),
  };
  var audioTrack: TimelineTrack = {
    id: "audio",
    label: "Audio",
    kind: "audio",
    clips: audioClips.map(function (a) { return { id: a.id, label: a.label, duration_seconds: a.duration_seconds }; }),
  };
  var musicTrack: TimelineTrack = {
    id: "music",
    label: "Music",
    kind: "music",
    clips: musicClips.map(function (m) { return { id: m.id, label: m.label, duration_seconds: m.duration_seconds }; }),
  };
  var transcriptTrack: TimelineTrack = {
    id: "transcript",
    label: "字幕",
    kind: "transcript",
    clips: transcriptClips.map(function (t) { return { id: t.id, label: t.label, duration_seconds: t.duration_seconds, scene_index: t.scene_index }; }),
  };

  var tracks: TimelineTrack[] = [sceneTrack, transcriptTrack, audioTrack, musicTrack];

  function renderClip(c: { id: string; label: string; duration_seconds: number; scene_index?: number }, kind: TimelineTrack["kind"]) {
    var w = Math.max(40, (c.duration_seconds || 1) * 60 * zoom);
    return (
      <div
        key={c.id}
        className={"tl-clip " + kind}
        style={{ width: w + "px" }}
        onClick={function () { if (c.id) clickScene(c.id); }}
        title={c.label + " · " + (c.duration_seconds || 0) + "s"}
      >
        {kind === "scene" && <span className="idx">{(c.scene_index || 0) + 1}</span>}
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.label}</span>
        <span className="dur">{(c.duration_seconds || 0).toFixed(1)}s</span>
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
          <button className={view === "basic" ? "active" : ""} onClick={function () { setView("basic"); }}>Basic</button>
          <button className={view === "timeline" ? "active" : ""} onClick={function () { setView("timeline"); }}>Timeline</button>
        </div>
      </div>

      <div className="tl-tracks">
        {tracks.map(function (tr) {
          return (
            <div key={tr.id} className="tl-track">
              <div className="tl-track-label">{tr.label}<small>{tr.clips.length} clip</small></div>
              <div className="tl-strip">
                {tr.clips.length === 0 ? <span className="tl-empty">空轨道</span> : tr.clips.map(function (c) { return renderClip(c, tr.kind); })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="tl-summary">
        <span className="label">总时长</span><strong>{formatTime(totalDuration)}</strong>
        <span className="label">场景</span><strong>{scenes.length}</strong>
        <span className="label">声音</span><strong>{voiceCount}</strong>
        <span className="label">音乐</span><strong>{musicClips.length}</strong>
        <span className="label">字幕轨</span><strong>{transcriptClips.length}</strong>
        {props.onAddScene && <button className="tl-add" onClick={props.onAddScene}>+ 新增场景</button>}
      </div>
    </section>
  );
}

export default Timeline;
