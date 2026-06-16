import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { KPIStatGrid, Tabs, EmptyState, Modal } from "../components/ui";
import { useToast } from "../components/ui/toast";
import NewsCard from "../components/NewsCard";
import BarChart from "../components/charts/BarChart";
import { useGlobalSearch } from "../search";
import { newsCategory, newsSummary, sourceMeta } from "../lib/news";
import { ageLabel } from "../lib/time";
import type { NewsArticle } from "../api/types";

export default function Collect() {
  const qc = useQueryClient();
  const toast = useToast();
  const [view, setView] = useState<"browse" | "settings">("browse");
  const [cat, setCat] = useState<"keyword" | "portal">("keyword");
  const [chan, setChan] = useState<string>("전체");
  const [open, setOpen] = useState<NewsArticle | null>(null);
  const { query } = useGlobalSearch();
  const q = query.trim().toLowerCase();

  const news = useQuery({ queryKey: ["news", 30], queryFn: () => api.news.list({ days: 30, limit: 300 }) });
  const today = useQuery({ queryKey: ["news", "today"], queryFn: () => api.news.today() });
  const all = news.data ?? [];

  const cats = useMemo(() => all.filter((a) => newsCategory(a.source) === cat), [all, cat]);
  const channels = useMemo(() => ["전체", ...Array.from(new Set(cats.map((a) => sourceMeta(a.source).label)))], [cats]);
  const items = cats.filter((a) =>
    (chan === "전체" || sourceMeta(a.source).label === chan) &&
    (!q || `${a.title} ${newsSummary(a)} ${a.keywords ?? ""}`.toLowerCase().includes(q)));

  const collect = useMutation({
    mutationFn: (kw: string[]) => api.collect.run(kw, { do_enrich: false }),
    onSuccess: (r) => { toast.push(`✅ ${r.total_articles}건 수집했어요`, "success"); qc.invalidateQueries({ queryKey: ["news"] }); },
    onError: (e) => toast.push(`⚠️ 수집 실패: ${(e as Error).message}`, "danger"),
  });

  const activeSources = new Set(all.map((a) => sourceMeta(a.source).label)).size;
  const lastUpdate = all[0]?.collected_at || all[0]?.date;

  return (
    <div>
      <KPIStatGrid items={[
        { label: "활성 출처", value: activeSources },
        { label: "오늘 수집", value: today.isLoading ? "…" : (today.data?.length ?? 0) },
        { label: "30일 누적", value: news.isLoading ? "…" : all.length },
        { label: "최종 갱신", value: lastUpdate ? ageLabel(lastUpdate) : "—" },
      ]} />

      <div className="cl-bar">
        <Tabs items={[{ key: "browse", label: "🃏 카드" }, { key: "settings", label: "⚙ 수집 설정" }]}
          value={view} onChange={(v) => setView(v as "browse" | "settings")} />
        <span className="cl-grow" />
        <CollectButton pending={collect.isPending} onRun={() => collect.mutate([])} />
      </div>

      {view === "browse" ? (
        <BrowseView cat={cat} setCat={(c) => { setCat(c); setChan("전체"); }}
          channels={channels} chan={chan} setChan={setChan} items={items} q={query} onOpen={setOpen}
          loading={news.isLoading} />
      ) : (
        <SettingsView onCollect={(kw) => collect.mutate(kw)} collecting={collect.isPending} />
      )}

      <ArticleModal article={open} onClose={() => setOpen(null)} />
    </div>
  );
}

function CollectButton({ pending, onRun }: { pending: boolean; onRun: () => void }) {
  return <button className="btn primary" disabled={pending} onClick={onRun}>{pending ? "수집 중…" : "🔄 지금 수집"}</button>;
}

function BrowseView({ cat, setCat, channels, chan, setChan, items, q, onOpen, loading }: {
  cat: "keyword" | "portal"; setCat: (c: "keyword" | "portal") => void;
  channels: string[]; chan: string; setChan: (c: string) => void;
  items: NewsArticle[]; q: string; onOpen: (a: NewsArticle) => void; loading: boolean;
}) {
  return (
    <>
      <Tabs items={[{ key: "keyword", label: "🔑 키워드 뉴스" }, { key: "portal", label: "🏛 뉴스 포탈" }]}
        value={cat} onChange={(c) => setCat(c as "keyword" | "portal")} />
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
      {q && <div className="muted" style={{ marginBottom: 8 }}>검색: "{q}" — {items.length}건</div>}
      {loading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
        : items.length === 0 ? <EmptyState icon="🗞" title="기사가 없어요" hint="‘지금 수집’으로 수집을 시작하세요." />
        : <div className="bd-grid">{items.slice(0, 48).map((a) => (
            <div key={a.link} onClick={(e) => { e.preventDefault(); onOpen(a); }}><NewsCard article={a} /></div>
          ))}</div>}
    </>
  );
}

function ArticleModal({ article, onClose }: { article: NewsArticle | null; onClose: () => void }) {
  if (!article) return null;
  const m = sourceMeta(article.source);
  return (
    <Modal open onClose={onClose} title={<span style={{ color: m.color }}>{m.label}</span>} width={620}>
      <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>{ageLabel(article.collected_at || article.date)}</div>
      <h2 style={{ margin: "8px 0", fontSize: "var(--fs-headline)" }}>{article.title}</h2>
      <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{newsSummary(article) || "본문 요약이 아직 없어요."}</div>
      {article.keywords && <div style={{ marginTop: 10 }}>{article.keywords.split(",").map((k) => <span key={k} className="chip">{k.trim()}</span>)}</div>}
      <div style={{ marginTop: 16 }}>
        {article.link && <a className="btn primary" href={article.link} target="_blank" rel="noreferrer noopener">원본 기사 열기 ↗</a>}
      </div>
    </Modal>
  );
}

function SettingsView({ onCollect, collecting }: { onCollect: (kw: string[]) => void; collecting: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(""); const [url, setUrl] = useState("");
  const [diagUrl, setDiagUrl] = useState(""); const [kw, setKw] = useState("");
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.sources.list() });
  const status = useQuery({ queryKey: ["collect", "status"], queryFn: () => api.collect.status() });

  const toggle = useMutation({ mutationFn: (n: string) => api.sources.toggle(n), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const add = useMutation({ mutationFn: () => api.sources.add(name, url), onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); setName(""); setUrl(""); toast.push("출처 추가됨", "success"); }, onError: (e) => toast.push((e as Error).message, "danger") });
  const remove = useMutation({ mutationFn: (n: string) => api.sources.remove(n), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const diag = useMutation({ mutationFn: () => api.collect.diagnose(diagUrl) });

  const daily = (status.data?.daily ?? []) as (string | null)[];
  const bars = daily.map((s, i) => ({ label: String(i), value: s ? 1 : 0, title: s ?? "수집 없음", highlight: i === daily.length - 1 }));

  return (
    <div>
      <div className="card">
        <div className="card-title">⚡ 빠른 수집</div>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="cl-search" value={kw} onChange={(e) => setKw(e.target.value)} placeholder="키워드(쉼표) 예: 용접 로봇, 디지털 트윈" />
          <button className="btn primary" disabled={collecting} onClick={() => onCollect(kw.split(",").map((s) => s.trim()).filter(Boolean))}>{collecting ? "수집 중…" : "수집"}</button>
        </div>
      </div>

      <div className="card">
        <div className="card-title">출처 설정</div>
        {sources.data?.items.map((s) => (
          <div className="cl-src" key={s.name}>
            <span className="cl-chip-dot" style={{ background: sourceMeta(s.name).color }} />
            <span className="cl-src-name">{s.name}{s.custom && <span className="cl-src-url"> · {s.url}</span>}</span>
            {s.custom && <button className="btn" onClick={() => remove.mutate(s.name)}>제거</button>}
            <button className={`cl-toggle${s.enabled ? " on" : ""}`} onClick={() => toggle.mutate(s.name)} aria-label="toggle" />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input className="cl-search" value={name} onChange={(e) => setName(e.target.value)} placeholder="출처 이름" style={{ flex: "0 0 140px" }} />
          <input className="cl-search" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="RSS URL" />
          <button className="btn" disabled={!name || !url || add.isPending} onClick={() => add.mutate()}>＋ 등록</button>
        </div>
      </div>

      <div className="card">
        <div className="card-title">수집 이력 <span className="muted" style={{ fontWeight: 400 }}>· 최근 14일</span></div>
        {bars.length > 0 ? <BarChart bars={bars} width={520} height={60} /> : <div className="muted">이력 없음</div>}
        {status.data?.latest ? <div className="muted" style={{ marginTop: 8, fontSize: "var(--fs-caption)" }}>
          최근: {JSON.stringify(status.data.latest).slice(0, 80)}</div> : null}
      </div>

      <div className="card">
        <div className="card-title">🔬 기사 진단</div>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="cl-search" value={diagUrl} onChange={(e) => setDiagUrl(e.target.value)} placeholder="기사 URL" />
          <button className="btn" disabled={!diagUrl || diag.isPending} onClick={() => diag.mutate()}>{diag.isPending ? "진단 중…" : "진단"}</button>
        </div>
        {diag.data && <div className="cl-diag">{JSON.stringify(diag.data, null, 2)}</div>}
        {diag.error && <div style={{ color: "var(--semantic-danger)", marginTop: 8 }}>{(diag.error as Error).message}</div>}
      </div>
    </div>
  );
}
