import { useSyncExternalStore } from "react";

// 전역 뉴스 검색어 — Topbar 입력 → 뉴스 수집 화면이 소비 (ui 의 _news_search_q 승계).
let query = "";
const listeners = new Set<() => void>();

export function setGlobalSearch(q: string) {
  query = q;
  listeners.forEach((l) => l());
}

export function useGlobalSearch(): { query: string; setQuery: (q: string) => void } {
  const q = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => query,
    () => query,
  );
  return { query: q, setQuery: setGlobalSearch };
}
