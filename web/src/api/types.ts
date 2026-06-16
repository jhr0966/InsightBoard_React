// API 계약 타입.
//
// 두 갈래:
//  (1) pydantic 모델 응답 → `schema.ts`(openapi-typescript 자동생성)에서 **alias** →
//      서버 스키마가 바뀌면 타입도 자동으로 바뀐다(드리프트 제거).
//      재생성: `python scripts/gen_openapi.py && cd web && npm run gen:types`
//  (2) dict 를 그대로 반환하는 엔드포인트(news/trends/opportunities/threads 등)는
//      OpenAPI 에 named schema 가 없으므로 손수 유지(아래 hand-written).
import type { components } from "./schema";

type S = components["schemas"];

// (1) 자동생성 스키마 alias
export type TaskDef = S["TaskDefOut"];
export type Bookmark = S["BookmarkOut"];
export type ChatMessage = S["ChatMessage"];
export type Persona = S["PersonaModel"];
export type Prefs = S["PrefsModel"];

export interface Audited {
  user_id: string;
  workspace_id: string;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// (2) dict 반환 엔드포인트 — 손수 유지
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

export interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  pinned: boolean;
}
