// 타입드 fetch 클라이언트 — FastAPI api/ 계약 소비.
// base: 빈 값이면 동일 출처(/api). dev 는 vite proxy 가 8000 으로 전달.
import type {
  AssistantContext,
  Bookmark,
  ChatMessage,
  DayCount,
  IngestResult,
  KeywordCount,
  NewsArticle,
  OpportunityCell,
  Persona,
  Prefs,
  SourceCount,
  TaskDef,
  Thread,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const qs = (params: Record<string, unknown>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => req<{ status: string; phase: string }>("/api/health"),

  board: {
    brief: (days = 1) =>
      req<{ brief: string; item_count: number; persona_label: string }>(
        `/api/board/brief${qs({ days })}`,
      ),
  },

  taskdefs: {
    list: (q?: { team?: string; dept?: string; q?: string; limit?: number }) =>
      req<TaskDef[]>(`/api/taskdefs${qs(q ?? {})}`),
    get: (id: string) => req<TaskDef>(`/api/taskdefs/${encodeURIComponent(id)}`),
    upsert: (id: string, body: { json: Record<string, unknown>; task_def_text?: string }) =>
      req<TaskDef>(`/api/taskdefs/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    remove: (id: string) =>
      req<{ deleted: boolean }>(`/api/taskdefs/${encodeURIComponent(id)}`, { method: "DELETE" }),
    upload: async (file: File, replace = false): Promise<IngestResult> => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${BASE}/api/taskdefs/upload?replace=${replace}`, {
        method: "POST",
        body: fd, // multipart — Content-Type 자동 설정(boundary)
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`${res.status} ${detail}`);
      }
      return (await res.json()) as IngestResult;
    },
  },

  opportunities: {
    list: (days = 30, top = 20) =>
      req<OpportunityCell[]>(`/api/opportunities${qs({ days, top })}`),
  },

  bookmarks: {
    list: (type?: string) => req<Bookmark[]>(`/api/bookmarks${qs({ type })}`),
    summary: () => req<Record<string, unknown>>("/api/bookmarks/summary"),
    create: (body: Partial<Bookmark> & { type: string; title: string }) =>
      req<Bookmark>("/api/bookmarks", { method: "POST", body: JSON.stringify(body) }),
    setStatus: (id: string, status: string, note = "") =>
      req<Bookmark>(`/api/bookmarks/${encodeURIComponent(id)}/status`, {
        method: "POST",
        body: JSON.stringify({ status, note }),
      }),
    remove: (id: string) =>
      req<{ deleted: boolean }>(`/api/bookmarks/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },

  news: {
    list: (q?: { days?: number; source?: string; limit?: number }) =>
      req<NewsArticle[]>(`/api/news${qs(q ?? {})}`),
    today: () => req<NewsArticle[]>("/api/news/today"),
  },

  trends: {
    keywords: (days = 7, top = 20) => req<KeywordCount[]>(`/api/trends/keywords${qs({ days, top })}`),
    volume: (days = 7) => req<DayCount[]>(`/api/trends/volume${qs({ days })}`),
    sources: (days = 7) => req<SourceCount[]>(`/api/trends/sources${qs({ days })}`),
    emergence: (base_days = 30, top = 20) =>
      req<{ new: KeywordCount[]; rising: { keyword: string; today: number; base: number; delta: number }[] }>(
        `/api/trends/emergence${qs({ base_days, top })}`,
      ),
  },

  matches: {
    list: (days = 7, top_k = 5) => req<Record<string, unknown>[]>(`/api/matches${qs({ days, top_k })}`),
  },

  insights: {
    heatmap: (days = 30) =>
      req<{ rows: string[]; cols: string[]; data: number[][] }>(`/api/insights/heatmap${qs({ days })}`),
  },

  sources: {
    list: () => req<{ items: { name: string; enabled: boolean; custom: boolean; url: string | null }[] }>("/api/sources"),
    toggle: (name: string) => req(`/api/sources/${encodeURIComponent(name)}/toggle`, { method: "POST" }),
    add: (name: string, url: string) =>
      req("/api/sources", { method: "POST", body: JSON.stringify({ name, url }) }),
    remove: (name: string) => req(`/api/sources/${encodeURIComponent(name)}`, { method: "DELETE" }),
  },

  proposals: {
    generate: (task: Record<string, unknown>, opts?: { days?: number; max_news?: number }) =>
      req<{ proposal: string; task_process_id: string | null }>("/api/proposals/generate", {
        method: "POST",
        body: JSON.stringify({ task, ...opts }),
      }),
  },

  assistant: {
    status: () => req<{ configured: boolean; provider: string }>("/api/assistant/status"),
    context: (screen: string, days = 7) =>
      req<AssistantContext>(`/api/assistant/context${qs({ screen, days })}`),
  },

  threads: {
    list: () => req<Thread[]>("/api/threads"),
    create: (title = "") =>
      req<Thread>("/api/threads", { method: "POST", body: JSON.stringify({ title }) }),
    get: (id: string) => req<Thread>(`/api/threads/${encodeURIComponent(id)}`),
    update: (id: string, body: { title?: string; pinned?: boolean }) =>
      req<Thread>(`/api/threads/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id: string) =>
      req<{ deleted: boolean }>(`/api/threads/${encodeURIComponent(id)}`, { method: "DELETE" }),
    messages: (id: string) => req<ChatMessage[]>(`/api/threads/${encodeURIComponent(id)}/messages`),
    saveMessages: (id: string, messages: ChatMessage[]) =>
      req<{ ok: boolean; count: number }>(`/api/threads/${encodeURIComponent(id)}/messages`, {
        method: "PUT",
        body: JSON.stringify({ messages }),
      }),
  },

  persona: {
    get: () => req<Persona>("/api/persona"),
    save: (body: Partial<Persona>) =>
      req<Persona>("/api/persona", { method: "PUT", body: JSON.stringify(body) }),
    derive: () => req<Persona>("/api/persona/derive", { method: "POST" }),
    reset: () => req<Persona>("/api/persona/reset", { method: "POST" }),
  },

  prefs: {
    get: () => req<Prefs>("/api/ui-prefs"),
    save: (theme: string, font: string) =>
      req<Prefs>("/api/ui-prefs", { method: "PUT", body: JSON.stringify({ theme, font }) }),
  },

  collect: {
    run: (keywords: string[], opts?: { sources?: string[]; max_results?: number; do_enrich?: boolean }) =>
      req<{ total_articles: number; total_files: number; saved: unknown[]; errors: string[] }>(
        "/api/collect",
        { method: "POST", body: JSON.stringify({ keywords, ...opts }) },
      ),
    status: () => req<{ latest: Record<string, unknown> | null; daily: (string | null)[] }>("/api/collect/status"),
    runs: (limit = 12) => req<Record<string, unknown>[]>(`/api/collect/runs${qs({ limit })}`),
    diagnose: (url: string) =>
      req<Record<string, unknown>>("/api/collect/diagnose", { method: "POST", body: JSON.stringify({ url }) }),
  },

  proposalsExtra: {
    summarize: (days = 3) =>
      req<{ summary: string; news_count: number }>("/api/proposals/summarize", {
        method: "POST",
        body: JSON.stringify({ days }),
      }),
  },
};

// SSE 챗 스트림 — onDelta 로 토큰 조각 전달. AbortSignal 로 취소.
export async function streamChat(
  messages: ChatMessage[],
  onDelta: (text: string) => void,
  opts?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(`${BASE}/api/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal: opts?.signal,
  });
  if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const payload = JSON.parse(line.slice(5).trim()) as {
        delta?: string;
        done?: boolean;
        error?: string;
      };
      if (payload.error) throw new Error(payload.error);
      if (payload.delta) onDelta(payload.delta);
      if (payload.done) return;
    }
  }
}
