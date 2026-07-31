import { useEffect, useState } from "react";
import { listTemplateCategories, listTemplates } from "./drafts";
import type { TemplateCategory, TemplateMeta } from "./drafts";

export type TemplateCatalog = {
  templates: TemplateMeta[];
  categories: TemplateCategory[];
  status: "idle" | "loading" | "ready" | "error";
};

export type TemplateCacheSnapshot = TemplateCatalog & { refresh: () => void };

// P1 共享缓存: 多个组件 (App / Composer) 共用一次 `/templates` + `/templates/categories` 请求.
// 单飞: in-flight promise 复用, 避免双 fetch; 失败时仅首次重试 1 次 (100ms).
let inFlight: Promise<TemplateCatalog> | null = null;
let cached: TemplateCatalog = {
  templates: [],
  categories: [],
  status: "idle",
};
const subscribers = new Set<(snapshot: TemplateCatalog) => void>();

function emit(next: TemplateCatalog) {
  cached = next;
  for (const listener of subscribers) listener(next);
}

async function loadOnce(): Promise<TemplateCatalog> {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    try {
      const [nextCategories, nextTemplates] = await Promise.all([
        listTemplateCategories(),
        listTemplates(),
      ]);
      const next: TemplateCatalog = {
        templates: nextTemplates || [],
        categories: nextCategories || [],
        status: "ready",
      };
      emit(next);
      return next;
    } catch (error) {
      emit({ ...cached, status: "error" });
      throw error;
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

export async function refreshTemplateCatalog(): Promise<TemplateCatalog> {
  return loadOnce();
}

export function getTemplateCatalogSnapshot(): TemplateCatalog {
  return cached;
}

export function subscribeTemplateCache(listener: (snapshot: TemplateCatalog) => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}

// P1: 失败一次后 100ms 重试一次, 解决 dev reload 早期 fetch abort → catalog 永远空
let retries = 0;
export function loadTemplateCatalogWithRetry(): void {
  emit({ ...cached, status: "loading" });
  loadOnce()
    .then(() => {
      retries = 0;
    })
    .catch(() => {
      if (retries < 1) {
        retries += 1;
        setTimeout(() => loadTemplateCatalogWithRetry(), 100);
      }
    });
}

export function useTemplateCache(initial: TemplateCacheSnapshot): TemplateCacheSnapshot {
  const [snapshot, setSnapshot] = useState<TemplateCatalog>(initial);
  useEffect(() => {
    // 初次挂载同步外部 initial (避免 SSR/水合延迟)
    setSnapshot(initial);
    const unsubscribe = subscribeTemplateCache(setSnapshot);
    return () => {
      unsubscribe();
    };
    // initial 仅用于首次同步, 后续依赖 subscribers 的 emit
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return {
    ...snapshot,
    refresh: () => {
      void refreshTemplateCatalog();
    },
  };
}
