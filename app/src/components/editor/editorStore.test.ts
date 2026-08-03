import { describe, it, expect, beforeEach } from "vitest";
import { editorActions, editorStore, DEFAULT_LAYERS } from "./editorStore";

function getState() {
  return editorStore.getState();
}

describe("editorStore / editorActions", () => {
  beforeEach(() => {
    editorActions.reset();
  });

  it("toggleLayer flips visibility of the matching layer", () => {
    const target = DEFAULT_LAYERS[0].id;
    const before = getState().layers.find((l) => l.id === target)!.visible;
    editorActions.toggleLayer(target);
    const after = getState().layers.find((l) => l.id === target)!.visible;
    expect(after).toBe(!before);
  });

  it("setLayerOpacity updates only the matching layer", () => {
    const target = DEFAULT_LAYERS[1].id;
    editorActions.setLayerOpacity(target, 42);
    const l = getState().layers.find((x) => x.id === target)!;
    expect(l.opacity).toBe(42);
    const other = getState().layers.find((x) => x.id === DEFAULT_LAYERS[0].id)!;
    expect(other.opacity).not.toBe(42);
  });

  it("lockLayer toggles locked flag", () => {
    const target = DEFAULT_LAYERS[2].id;
    const before = getState().layers.find((l) => l.id === target)!.locked;
    editorActions.lockLayer(target);
    expect(getState().layers.find((l) => l.id === target)!.locked).toBe(!before);
  });

  it("reorderLayers moves src before target and is a no-op when src==target", () => {
    const ids = getState().layers.map((l) => l.id);
    editorActions.reorderLayers(ids[0], ids[3]);
    expect(getState().layers.map((l) => l.id)).toEqual([ids[1], ids[2], ids[3], ids[0], ids[4], ids[5]]);
    editorActions.reorderLayers(ids[3], ids[3]);
    expect(getState().layers.map((l) => l.id)).toEqual([ids[1], ids[2], ids[3], ids[0], ids[4], ids[5]]);
  });

  it("addLayer appends a new layer with default name+kind", () => {
    const before = getState().layers.length;
    editorActions.addLayer();
    const after = getState().layers;
    expect(after.length).toBe(before + 1);
    expect(after[after.length - 1].kind).toBe("element");
    expect(after[after.length - 1].opacity).toBe(100);
  });

  it("removeLayer deletes by id", () => {
    const target = DEFAULT_LAYERS[1].id;
    const before = getState().layers.length;
    editorActions.removeLayer(target);
    const after = getState().layers;
    expect(after.length).toBe(before - 1);
    expect(after.find((l) => l.id === target)).toBeUndefined();
  });

  it("flipLayers reverses the order", () => {
    const ids = getState().layers.map((l) => l.id);
    editorActions.flipLayers();
    expect(getState().layers.map((l) => l.id)).toEqual([...ids].reverse());
  });

  it("addElement + removeElement + setElementOpacity mutate the elements array", () => {
    editorActions.addElement({ id: "el1", position: "top-left", size: 50, opacity: 80, width: 100, height: 100, x: 100, y: 100 });
    editorActions.addElement({ id: "el2", position: "center", size: 30, opacity: 100, width: 200, height: 200, x: 540, y: 260 });
    const id = getState().elements[0].id;
    editorActions.setElementOpacity(id, 25);
    expect(getState().elements[0].opacity).toBe(25);
    editorActions.removeElement(id);
    expect(getState().elements.length).toBe(1);
  });

  it("selectCharacter + clearCharacter toggle character slot", () => {
    expect(getState().character).toBeNull();
    editorActions.selectCharacter({ id: "emma_de", name: "Emma", style: "新闻", region: "DE", start_seconds: 0 });
    expect(getState().character?.id).toBe("emma_de");
    editorActions.clearCharacter();
    expect(getState().character).toBeNull();
  });

  it("togglePlay + setPlayhead update playing + playhead", () => {
    expect(getState().playing).toBe(false);
    editorActions.togglePlay();
    expect(getState().playing).toBe(true);
    editorActions.setPlayhead(12.5);
    expect(getState().playhead).toBe(12.5);
  });

  it("reset() restores DEFAULT_LAYERS + null character", () => {
    editorActions.toggleLayer(DEFAULT_LAYERS[0].id);
    editorActions.addElement({ position: "top-right", size: 10, opacity: 10, width: 50, height: 50, x: 0, y: 0 });
    editorActions.selectCharacter({ id: "x", name: "X", style: "X", region: "X", start_seconds: 0 });
    editorActions.reset();
    const s = getState();
    expect(s.layers.length).toBe(DEFAULT_LAYERS.length);
    expect(s.character).toBeNull();
    expect(s.elements.length).toBe(0);
    expect(s.layers[0].visible).toBe(DEFAULT_LAYERS[0].visible);
  });

  it("setElementGeometry mutates only the specified fields (pixel-level drag-resize)", () => {
    editorActions.addElement({ id: "g1", position: "center", size: 100, opacity: 100, width: 200, height: 200, x: 540, y: 260 });
    // 改 width
    editorActions.setElementGeometry("g1", { width: 320 });
    let g = getState().elements[0];
    expect(g.width).toBe(320);
    expect(g.height).toBe(200);
    expect(g.x).toBe(540);
    expect(g.y).toBe(260);
    // 改 x/y
    editorActions.setElementGeometry("g1", { x: 100, y: 50 });
    g = getState().elements[0];
    expect(g.x).toBe(100);
    expect(g.y).toBe(50);
    expect(g.width).toBe(320);
    // 不存在的 id 是 no-op
    const before = getState().elements.length;
    editorActions.setElementGeometry("does-not-exist", { width: 999 });
    expect(getState().elements.length).toBe(before);
  });

});
