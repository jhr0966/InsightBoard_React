// 타입드 fetch 클라이언트 — FastAPI api/ 계약 소비.
// base: 빈 값이면 동일 출처(/api). dev 는 vite proxy 가 8000 으로 전달.
import type {
  AssistantContext,
  Bookmark,
  ChatMessage,
  DayCount,
  KeywordCount,
  NewsArticle,
  SourceCount,
  TaskDef,
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
