// Editor 11 面板 SharedState 中心: 一个轻量 store (类 zustand).
// 没有外部依赖; React 19 useSyncExternalStore 兼容.
import { useSyncExternalStore } from "react";

export type LayerKind = "background" | "video" | "avatar" | "element" | "subtitle" | "watermark";

export type Layer = {
  id: string;
  name: string;
  kind: LayerKind;
  visible: boolean;
  opacity: number;
  locked: boolean;
};

export type ElementChoice = {
  id: string;
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "center";
  size: number;
  opacity: number;
  // P2 drag-resize: 像素级 width/height + x/y 偏移 (基于 1280x720 画布)
  width: number;
  height: number;
  x: number;
  y: number;
};

export type CharacterChoice = {
  id: string;
  name: string;
  style: string;
  region: string;
  start_seconds: number;
};

export type EditorState = {
  layers: Layer[];
  elements: ElementChoice[];
  character: CharacterChoice | null;
  selected_scene_id: string | null;
  playing: boolean;
  playhead: number;
};

const KIND_COLOR: Record<LayerKind, string> = {
  background: "#5b6cff",
  video: "#48d58b",
  avatar: "#f5a524",
  element: "#19b5c5",
  subtitle: "#7bd0ff",
  watermark: "#94a3b8",
};

const KIND_ICON: Record<LayerKind, string> = {
  background: "▢",
  video: "▶",
  avatar: "◎",
  element: "◇",
  subtitle: "T",
  watermark: "©",
};

export const DEFAULT_LAYERS: Layer[] = [
  { id: "l1", name: "背景",     kind: "background", visible: true, opacity: 100, locked: false },
  { id: "l2", name: "主视频",   kind: "video",      visible: true, opacity: 100, locked: false },
  { id: "l3", name: "数字人",   kind: "avatar",     visible: true, opacity: 100, locked: false },
  { id: "l4", name: "装饰元素", kind: "element",    visible: true, opacity: 80,  locked: false },
  { id: "l5", name: "字幕",     kind: "subtitle",   visible: true, opacity: 100, locked: false },
  { id: "l6", name: "水印",     kind: "watermark",  visible: true, opacity: 35,  locked: true },
];

const initial: EditorState = {
  layers: DEFAULT_LAYERS,
  elements: [],
  character: null,
  selected_scene_id: null,
  playing: false,
  playhead: 0,
};

let state: EditorState = initial;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function getState(): EditorState {
  return state;
}

function setState(updater: (prev: EditorState) => EditorState) {
  const next = updater(state);
  if (next === state) return;
  state = next;
  emit();
}

export const editorStore = {
  getState,
  subscribe,
  setState,
  kindColor: KIND_COLOR,
  kindIcon: KIND_ICON,
};

export function useEditorState<T>(selector: (s: EditorState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(getState()),
    () => selector(initial),
  );
}

export function useEditor(): EditorState {
  return useSyncExternalStore(subscribe, getState, () => initial);
}

export const editorActions = {
  toggleLayer(id: string) {
    setState((s) => ({ ...s, layers: s.layers.map((l) => l.id === id ? { ...l, visible: !l.visible } : l) }));
  },
  setLayerOpacity(id: string, opacity: number) {
    setState((s) => ({ ...s, layers: s.layers.map((l) => l.id === id ? { ...l, opacity } : l) }));
  },
  lockLayer(id: string) {
    setState((s) => ({ ...s, layers: s.layers.map((l) => l.id === id ? { ...l, locked: !l.locked } : l) }));
  },
  removeLayer(id: string) {
    setState((s) => ({ ...s, layers: s.layers.filter((l) => l.id !== id) }));
  },
  addLayer(layer?: Partial<Layer>) {
    setState((s) => {
      const next: Layer = {
        id: "l" + (s.layers.length + 1) + "-" + Date.now().toString(36),
        name: layer && layer.name ? layer.name : "新图层 " + (s.layers.length + 1),
        kind: layer && layer.kind ? layer.kind : "element",
        visible: !layer || layer.visible !== false,
        opacity: layer && layer.opacity != null ? layer.opacity : 100,
        locked: layer ? !!layer.locked : false,
      };
      return { ...s, layers: s.layers.concat(next) };
    });
  },
  reorderLayers(srcId: string, targetId: string) {
    setState((s) => {
      if (srcId === targetId) return s;
      const srcIndex = s.layers.findIndex((l) => l.id === srcId);
      const targetIndex = s.layers.findIndex((l) => l.id === targetId);
      if (srcIndex < 0 || targetIndex < 0) return s;
      const next = s.layers.slice();
      const moved = next.splice(srcIndex, 1)[0];
      next.splice(targetIndex, 0, moved);
      return { ...s, layers: next };
    });
  },
  setLayerVisibilityAll(visible: boolean) {
    setState((s) => ({ ...s, layers: s.layers.map((l) => ({ ...l, visible })) }));
  },
  flipLayers() {
    setState((s) => ({ ...s, layers: [...s.layers].reverse() }));
  },
  addElement(el: Omit<ElementChoice, "id"> & { id?: string }) {
    setState((s) => {
      const next: ElementChoice = {
        id: el.id || "e" + Date.now().toString(36),
        position: el.position,
        size: el.size,
        opacity: el.opacity,
        width: el.width ?? 200,
        height: el.height ?? 200,
        x: el.x ?? 540,
        y: el.y ?? 260,
      };
      return { ...s, elements: s.elements.concat(next) };
    });
  },
  removeElement(id: string) {
    setState((s) => ({ ...s, elements: s.elements.filter((e) => e.id !== id) }));
  },
  setElementOpacity(id: string, opacity: number) {
    setState((s) => ({ ...s, elements: s.elements.map((e) => e.id === id ? { ...e, opacity } : e) }));
  },
  setElementSize(id: string, size: number) {
    setState((s) => ({ ...s, elements: s.elements.map((e) => e.id === id ? { ...e, size } : e) }));
  },
  // P2 drag-resize: 像素级 width/height + x/y 镜像到 Timeline mirror tracks
  setElementGeometry(id: string, geom: { width?: number; height?: number; x?: number; y?: number }) {
    setState((s) => ({
      ...s,
      elements: s.elements.map((e) => e.id === id
        ? { ...e, ...(geom.width != null ? { width: geom.width } : {}), ...(geom.height != null ? { height: geom.height } : {}), ...(geom.x != null ? { x: geom.x } : {}), ...(geom.y != null ? { y: geom.y } : {}) }
        : e),
    }));
  },
  selectCharacter(c: CharacterChoice) {
    setState((s) => ({ ...s, character: c }));
  },
  clearCharacter() {
    setState((s) => ({ ...s, character: null }));
  },
  setSelectedScene(id: string | null) {
    setState((s) => ({ ...s, selected_scene_id: id }));
  },
  togglePlay() {
    setState((s) => ({ ...s, playing: !s.playing }));
  },
  setPlayhead(p: number) {
    setState((s) => ({ ...s, playhead: p }));
  },
  reset() {
    setState(() => ({ ...initial, layers: DEFAULT_LAYERS.map((l) => ({ ...l })) }));
  },
};

if (typeof window !== "undefined" && (window as any)) {
  (window as any).__editorStore = editorStore;
  (window as any).__editorActions = editorActions;
}
