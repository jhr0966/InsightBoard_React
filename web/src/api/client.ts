// 타입드 fetch 클라이언트 — FastAPI api/ 계약 소비.
// base: 빈 값이면 동일 출처(/api). dev 는 vite proxy 가 8000 으로 전달.
import type {
  AssistantContext,
  Bookmark,
  CaseItem,
  ChatMessage,
  DayCount,
  IngestResult,
  UploadPreview,
  KeywordCount,
  KeywordSeries,
  DigestPage,
  NewsArticle,
  NewsListPage,
  ProposalEntity,
  OpportunityCell,
  ProcessMapCard,
  Persona,
  Prefs,
  SourceCount,
  TaskDef,
  Thread,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

// 무한 pending 방지 — Render 무료 콜드스타트(~50s)는 살리되, 그 이상 멈추면 에러로 전환.
// (타임아웃이 없으면 백엔드가 연결만 잡고 응답을 안 줄 때 쿼리가 영원히 로딩 상태로 남는다.)
const REQ_TIMEOUT_MS = 60_000;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQ_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
      signal: ctrl.signal,
    });
  } catch (err) {
    if (ctrl.signal.aborted) {
      throw new Error("서버 응답이 너무 늦어요 (무료 서버 콜드스타트일 수 있어요). 잠시 후 새로고침 해주세요.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
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
    // 개인화 다이제스트 — 기사 3~5건 + "왜 내 업무와 관련 있는가"(규칙 조합).
    digest: (limit = 5, days = 3) =>
      req<DigestPage>(`/api/board/digest${qs({ limit, days })}`),
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
    history: (id: string) =>
      req<{ id: number; action: string; changed_at: string; changed_by: string | null; source: string | null }[]>(
        `/api/taskdefs/${encodeURIComponent(id)}/history`,
      ),
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
    uploadPreview: async (file: File): Promise<UploadPreview> => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${BASE}/api/taskdefs/upload/preview`, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`${res.status} ${detail}`);
      }
      return (await res.json()) as UploadPreview;
    },
  },

  opportunities: {
    list: (days = 30, top = 20) =>
      req<OpportunityCell[]>(`/api/opportunities${qs({ days, top })}`),
  },

  bookmarks: {
    list: (type?: string, status?: string) => req<Bookmark[]>(`/api/bookmarks${qs({ type, status })}`),
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
    // 커서 페이지네이션 — 응답 {items, next_cursor}. cursor 는 이전 응답의 next_cursor.
    list: (q?: { days?: number; source?: string; limit?: number; cursor?: string }) =>
      req<NewsListPage>(`/api/news${qs(q ?? {})}`),
    today: () => req<NewsArticle[]>("/api/news/today"),
    contentRate: (days = 7) => req<{ total: number; ready: number; pct: number }>(`/api/news/content-rate${qs({ days })}`),
    detail: (link: string, days = 30) =>
      req<NewsArticle>(`/api/news/detail${qs({ link, days })}`),
  },

  cases: {
    list: (status?: string, technology_id?: string) =>
      req<CaseItem[]>(`/api/cases${qs({ status, technology_id })}`),
    summary: () => req<{ total: number; by_status: Record<string, number> }>("/api/cases/summary"),
    setStatus: (id: string, status: string) =>
      req<CaseItem>(`/api/cases/${encodeURIComponent(id)}/status`, {
        method: "POST", body: JSON.stringify({ status }),
      }),
    extract: (days = 7, limit = 10) =>
      req<{ attempted: number; extracted: number; failed?: number; reason?: string }>(
        "/api/cases/extract", { method: "POST", body: JSON.stringify({ days, limit }) }),
  },

  feedback: {
    // 노출/열람/저장/관련없음 이벤트 — 랭킹 평가·개인화 제외 목록의 원자료.
    send: (events: Record<string, unknown>[]) =>
      req<{ saved: number }>("/api/feedback/events", {
        method: "POST", body: JSON.stringify({ events }),
      }),
  },

  trends: {
    keywords: (days = 7, top = 20) => req<KeywordCount[]>(`/api/trends/keywords${qs({ days, top })}`),
    volume: (days = 7) => req<DayCount[]>(`/api/trends/volume${qs({ days })}`),
    sources: (days = 7) => req<SourceCount[]>(`/api/trends/sources${qs({ days })}`),
    keywordSeries: () => req<KeywordSeries>("/api/trends/keyword-series"),
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
    heatmapCell: (row: string, col: string, days = 30) =>
      req<NewsArticle[]>(`/api/insights/heatmap-cell${qs({ row, col, days })}`),
    processMap: (keyword: string, days = 30, top = 3) =>
      req<ProcessMapCard[]>(`/api/insights/process-map${qs({ keyword, days, top })}`),
  },

  sources: {
    list: () => req<{ items: { name: string; enabled: boolean; custom: boolean; url: string | null }[] }>("/api/sources"),
    health: (days = 7) => req<{ name: string; enabled: boolean; custom: boolean; count_7d: number; last_collected: string; status: string }[]>(`/api/sources/health${qs({ days })}`),
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
    // Proposal 엔터티(Step 13) — 상태 확장·이력·근거 관계 보존.
    save: (body: { title: string; content: string; task_id?: string;
      article_ids?: string[]; case_ids?: string[];
      matching_version?: number; prompt_version?: number; status?: string }) =>
      req<ProposalEntity>("/api/proposals/save", { method: "POST", body: JSON.stringify(body) }),
    listEntities: (status?: string) => req<ProposalEntity[]>(`/api/proposals/list${qs({ status })}`),
    summary: () => req<{ total: number; by_status: Record<string, number>; reviewing: number; adopted: number }>("/api/proposals/summary"),
    setStatus: (id: string, status: string, note = "") =>
      req<ProposalEntity>(`/api/proposals/${encodeURIComponent(id)}/status`, {
        method: "PATCH", body: JSON.stringify({ status, note }) }),
    history: (id: string) =>
      req<{ from_status: string; to_status: string; note: string; changed_by: string; changed_at: string }[]>(
        `/api/proposals/${encodeURIComponent(id)}/history`),
    removeEntity: (id: string) =>
      req<{ deleted: boolean }>(`/api/proposals/${encodeURIComponent(id)}`, { method: "DELETE" }),
    migrateBookmarks: () =>
      req<{ migrated: number; skipped: number }>("/api/proposals/migrate-bookmarks", { method: "POST" }),
    // 현재 제안서 MD + 지시 → 다듬은 MD (처음부터 재생성 없이 반복 개선).
    refine: (proposal: string, instruction: string) =>
      req<{ proposal: string }>("/api/proposals/refine", {
        method: "POST",
        body: JSON.stringify({ proposal, instruction }),
      }),
  },

  assistant: {
    status: () => req<{ configured: boolean; provider: string }>("/api/assistant/status"),
    context: (screen: string, query = "", days = 7) =>
      req<AssistantContext>(`/api/assistant/context${qs({ screen, query, days })}`),
  },

  threads: {
    list: () => req<Thread[]>("/api/threads"),
    // 문자열 title 또는 {first_message}(서버가 LLM 으로 제목 자동 생성) 둘 다 허용.
    create: (arg: string | { title?: string; first_message?: string } = "") =>
      req<Thread>("/api/threads", {
        method: "POST",
        body: JSON.stringify(typeof arg === "string" ? { title: arg } : arg),
      }),
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
    // 상세 수집 로그(디버깅) — 런 목록 + 단일 런 렌더 텍스트(복사용).
    logs: (limit = 20) =>
      req<{ run_id: string; meta: Record<string, unknown>; event_count: number }[]>(`/api/collect/logs${qs({ limit })}`),
    logDetail: (runId: string) =>
      req<{ run_id: string; meta: Record<string, unknown>; events: Record<string, unknown>[]; dropped: number; text: string }>(
        `/api/collect/logs/${encodeURIComponent(runId)}`),
  },

  proposalsExtra: {
    summarize: (days = 3) =>
      req<{ summary: string; news_count: number }>("/api/proposals/summarize", {
        method: "POST",
        body: JSON.stringify({ days }),
      }),
  },
};

// 수집 SSE 이벤트 — start | step | ping | done | error.
export interface CollectSaved { source: string; count: number; keywords?: string[]; sites?: Record<string, number>; }
export interface CollectErr { source?: string; keyword?: string; error: string; }
export interface CollectEvent {
  type: "start" | "step" | "enrich" | "ping" | "done" | "error";
  source?: string;
  keyword?: string;
  found?: number;
  done?: number;            // enrich 이벤트 — 본문 정리 완료 수
  total?: number;           // enrich 이벤트 — 본문 정리 대상 수(소스 검색 완료분 누적)
  run_id?: string;          // done 이벤트 — 방금 런의 상세 로그 id
  total_articles?: number;
  total_files?: number;
  saved?: CollectSaved[];
  errors?: CollectErr[];
  error?: string;
}

// 수집 SSE 스트림 — onEvent 로 진행 이벤트 전달. AbortSignal 로 취소.
export async function streamCollect(
  body: { keywords: string[]; sources?: string[]; max_results?: number; do_enrich?: boolean },
  onEvent: (e: CollectEvent) => void,
  opts?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(`${BASE}/api/collect/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts?.signal,
  });
  if (!res.ok || !res.body) throw new Error(`collect failed: ${res.status}`);
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
      onEvent(JSON.parse(line.slice(5).trim()) as CollectEvent);
    }
  }
}

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
