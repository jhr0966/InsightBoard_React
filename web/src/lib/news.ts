import type { NewsArticle } from "../api/types";

// 출처 라벨·색 (ui/data_management_render 승계, 토큰 기반 정리).
const SOURCE_META: Record<string, { label: string; color: string }> = {
  naver: { label: "네이버", color: "#03C75A" },
  google: { label: "구글", color: "#4285F4" },
  tech: { label: "AI Times", color: "#7C3AED" },
};
export function sourceMeta(source?: string): { label: string; color: string } {
  const s = (source || "").toLowerCase();
  for (const k of Object.keys(SOURCE_META)) if (s.includes(k)) return SOURCE_META[k];
  return { label: source || "기타", color: "#64748B" };
}

// http→https 승격, 비http면 빈 문자열(그라데이션 폴백).
export function httpsImg(url?: string): string {
  if (!url) return "";
  if (url.startsWith("https://")) return url;
  if (url.startsWith("http://")) return "https://" + url.slice(7);
  return "";
}

// 이미지 없을 때 제목 해시 기반 그라데이션.
export function gradientFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const a = h % 360;
  const b = (a + 40) % 360;
  return `linear-gradient(135deg, hsl(${a} 70% 62%), hsl(${b} 65% 52%))`;
}

export function newsSummary(a: NewsArticle): string {
  return (a.summary_llm || a.summary || "").trim();
}

// 대분류 — 키워드 뉴스(naver/google) vs 뉴스 포탈(tech/AI Times/오토메이션월드).
export function newsCategory(source?: string): "keyword" | "portal" {
  const s = (source || "").toLowerCase();
  return s.includes("naver") || s.includes("google") || s.includes("네이버") || s.includes("구글")
    ? "keyword" : "portal";
}
