import { useMemo, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Tabs, EmptyState, Modal } from "../components/ui";
import { useToast } from "../components/ui/toast";
import NewsCard from "../components/NewsCard";
import { useGlobalSearch } from "../search";
import { articleChannel, httpsImg, newsBody, newsCategory, newsSummary, sourceMeta } from "../lib/news";
import { ageLabel } from "../lib/time";
import type { NewsArticle } from "../api/types";

// 뉴스 탐색 (Step 11) — 콘텐츠 소비 전용 화면. 수집 실행·출처 관리는 /collect(관리).
// "부담 없이 읽는다": 카드 그리드 + 필터 칩 + 더 보기, 그 이상은 두지 않는다.
export default function Feed() {
  const toast = useToast();
  const [cat, setCat] = useState<"keyword" | "portal">("keyword");
  const [chan, setChan] = useState<string>("전체");
  const [open, setOpen] = useState<NewsArticle | null>(null);
  const { query } = useGlobalSearch();
  const q = query.trim().toLowerCase();

  // 커서 페이지네이션 — 60건씩 "더 보기"로 이어서 로드.
  const news = useInfiniteQuery({
    queryKey: ["news", 30],
    queryFn: ({ pageParam }) => api.news.list({ days: 30, limit: 60, cursor: pageParam || undefined }),
    initialPageParam: "",
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const all = useMemo(() => (news.data?.pages ?? []).flatMap((p) => p.items), [news.data]);

  const cats = useMemo(() => all.filter((a) => newsCategory(a.source) === cat), [all, cat]);
  const channels = useMemo(() => ["전체", ...Array.from(new Set(cats.map((a) => articleChannel(a).label)))], [cats]);
  const items = cats.filter((a) =>
    (chan === "전체" || articleChannel(a).label === chan) &&
    (!q || `${a.title} ${newsSummary(a)} ${a.keywords ?? ""}`.toLowerCase().includes(q)));

  const [summary, setSummary] = useState<string | null>(null);
  const summarize = useMutation({
    mutationFn: () => api.proposalsExtra.summarize(3),
    onSuccess: (d) => setSummary(d.summary?.trim() || "요약할 최근 뉴스가 없어요."),
    onError: (e) => toast.push((e as Error).message, "danger"),
  });

  const [mode, setMode] = useState<"card" | "table">("card");
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Tabs items={[{ key: "keyword", label: "🔑 키워드 뉴스" }, { key: "portal", label: "🏛 뉴스 포탈" }]}
          value={cat} onChange={(c) => { setCat(c as "keyword" | "portal"); setChan("전체"); }} />
        <span style={{ flex: 1 }} />
        <Tabs items={[{ key: "card", label: "🃏 카드" }, { key: "table", label: "📋 데이터 표" }]}
          value={mode} onChange={(m) => setMode(m as "card" | "table")} />
        <button className="btn" disabled={summarize.isPending} onClick={() => summarize.mutate()}>
          {summarize.isPending ? "요약 중…" : "📰 최근 뉴스 요약"}</button>
      </div>
      <div className="cl-chips">
        {channels.map((c) => {
          const m = c === "전체" ? { color: "var(--text-muted)" } : sourceMeta(c);
          return (
            <button key={c} className={`cl-chip${c === chan ? " on" : ""}`} onClick={() => setChan(c)}>
              {c !== "전체" && <span className="cl-chip-dot" style={{ background: m.color }} />}{c}
            </button>
          );
        })}
      </div>
      {q && <div className="muted" style={{ marginBottom: 8 }}>검색: "{q}" — {items.length}건 (로드된 기사 기준)</div>}
      {news.isLoading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
        : items.length === 0 ? <EmptyState icon="🗞" title="기사가 없어요" hint="수집 관리에서 수집을 시작하세요." />
        : mode === "table" ? <NewsTable items={items} onOpen={setOpen} />
        : <div className="bd-grid">{items.map((a) => (
            <div key={a.link} onClick={(e) => { e.preventDefault(); setOpen(a); }}><NewsCard article={a} /></div>
          ))}</div>}
      {!news.isLoading && news.hasNextPage && (
        <div style={{ textAlign: "center", marginTop: 12 }}>
          <button className="btn" disabled={news.isFetchingNextPage} onClick={() => news.fetchNextPage()}>
            {news.isFetchingNextPage ? "불러오는 중…" : "더 보기 ↓"}</button>
        </div>
      )}
      <ArticleModal article={open} onClose={() => setOpen(null)} />
      {summary !== null && (
        <Modal open onClose={() => setSummary(null)} title="📰 최근 뉴스 요약 (3일)" width={600}>
          <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: "var(--fs-body)" }}>{summary}</div>
        </Modal>
      )}
    </div>
  );
}

function NewsTable({ items, onOpen }: { items: NewsArticle[]; onOpen: (a: NewsArticle) => void }) {
  return (
    <div className="cl-table-wrap">
      <table className="cl-table">
        <thead><tr><th>출처</th><th>제목</th><th>본문</th><th>키워드</th><th>수집</th></tr></thead>
        <tbody>
          {items.map((a) => {
            const m = articleChannel(a);
            return (
              <tr key={a.link} onClick={() => onOpen(a)} style={{ cursor: "pointer" }}>
                <td><span className="cl-chip-dot" style={{ background: m.color }} /> {m.label}</td>
                <td className="cl-td-title">{a.title}</td>
                <td className="cl-td-sum">{newsBody(a) || <span className="muted">(본문 없음)</span>}</td>
                <td className="cl-td-kw">{(a.keywords_llm || a.keywords || "").split(",").slice(0, 3).join(", ")}</td>
                <td className="muted" style={{ whiteSpace: "nowrap" }}>{ageLabel(a.collected_at || a.date)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ArticleModal({ article, onClose }: { article: NewsArticle | null; onClose: () => void }) {
  // 목록은 발췌만 오므로 모달 열릴 때 상세(전체 본문)를 별도 조회.
  const detail = useQuery({
    queryKey: ["news", "detail", article?.link],
    queryFn: () => api.news.detail(article!.link),
    enabled: !!article?.link,
    staleTime: 5 * 60 * 1000,
  });
  if (!article) return null;
  const m = articleChannel(article);
  const full = detail.data ?? article;
  const body = newsBody(full);
  const kws = (full.keywords_llm || full.keywords || "").trim();
  const img = httpsImg(full.image_url);
  return (
    <Modal open onClose={onClose} title={<span style={{ color: m.color }}>{m.label}</span>} width={640}>
      {img && (
        <img src={img} alt="" loading="lazy"
          style={{ width: "100%", maxHeight: 260, objectFit: "cover", borderRadius: 8, marginBottom: 12 }}
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
      )}
      <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>
        {full.press ? `${full.press} · ` : ""}{ageLabel(full.collected_at || full.date)}
      </div>
      <h2 style={{ margin: "8px 0 12px", fontSize: "var(--fs-headline)", lineHeight: 1.35 }}>{full.title}</h2>
      {detail.isLoading ? (
        <div style={{ display: "grid", gap: 6 }}>{[0, 1, 2, 3].map((i) => <div key={i} className="skel" style={{ height: 14 }} />)}</div>
      ) : body ? (
        <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, maxHeight: 340, overflowY: "auto", fontSize: "var(--fs-body)" }}>{body}</div>
      ) : (
        <div className="muted" style={{ lineHeight: 1.6 }}>본문이 아직 수집되지 않았어요. 아래에서 원본을 확인하세요.</div>
      )}
      {kws && <div style={{ marginTop: 12 }}>{kws.split(",").map((k) => <span key={k} className="chip">{k.trim()}</span>)}</div>}
      <div style={{ marginTop: 16 }}>
        {article.link && <a className="btn primary" href={article.link} target="_blank" rel="noreferrer noopener">원본 기사 열기 ↗</a>}
      </div>
    </Modal>
  );
}
