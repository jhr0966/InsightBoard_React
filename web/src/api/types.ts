// FastAPI api/schemas.py 계약 미러 타입.
// (후속: openapi-typescript 로 자동 생성 권장 — 지금은 손수 미러)

export interface Audited {
  user_id: string;
  workspace_id: string;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TaskDef extends Audited {
  process_id: string;
  team: string | null;
  dept: string | null;
  division: string | null;
  process: string | null;
  task: string | null;
  json: Record<string, unknown> | null;
  task_def_text: string | null;
  updated_by: string | null;
}

export interface Bookmark extends Audited {
  id: string;
  type: "news" | "proposal" | "opportunity" | "task";
  title: string;
  content: string;
  link: string;
  tags: string[];
  status: "pending" | "adopted" | "rejected";
  decision_note: string;
  decided_at: string;
}

export interface NewsArticle {
  title: string;
  press?: string;
  date?: string;
  link: string;
  summary?: string;
  keywords?: string;
  source?: string;
  image_url?: string;
  summary_llm?: string;
  collected_at?: string;
}

export interface KeywordCount { keyword: string; count: number; }
export interface DayCount { date: string; count: number; }
export interface SourceCount { source: string; count: number; }

export interface OpportunityCell {
  dept: string;
  lv3: string;
  cell_score: number;
  avg_score: number;
  matched_news: number;
  matched_tasks: number;
  sample_tasks?: string;
  sample_news?: string;
}

export interface IngestResult {
  ok: boolean;
  errors: string[];
  row_count: number;
  sqlite_created: number;
  sqlite_updated: number;
  sqlite_skipped: number;
  sqlite_error: string;
}

export interface AssistantContext {
  screen: string;
  context: string;
  news_count: number;
}

export interface ChatMessage { role: "system" | "user" | "assistant"; content: string; }

export interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  pinned: boolean;
}
