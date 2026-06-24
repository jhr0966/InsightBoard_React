import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, streamCollect } from "../api/client";
import type { CollectEvent, CollectSaved, CollectErr } from "../api/client";
import { KPIStatGrid, Tabs, EmptyState, Modal, Badge } from "../components/ui";
import { useToast } from "../components/ui/toast";
import NewsCard from "../components/NewsCard";
import BarChart from "../components/charts/BarChart";
import { useGlobalSearch } from "../search";
import { articleChannel, httpsImg, newsCategory, newsSummary, sourceMeta } from "../lib/news";
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
  const channels = useMemo(() => ["전체", ...Array.from(new Set(cats.map((a) => articleChannel(a).label)))], [cats]);
  const items = cats.filter((a) =>
    (chan === "전체" || articleChannel(a).label === chan) &&
    (!q || `${a.title} ${newsSummary(a)} ${a.keywords ?? ""}`.toLowerCase().includes(q)));

  const [prog, setProg] = useState<CollectProgress | null>(null);
  const running = !!prog?.running;
  const runningRef = useRef(false);
  const [summary, setSummary] = useState<string | null>(null);
  const summarize = useMutation({
    mutationFn: () => api.proposalsExtra.summarize(3),
    onSuccess: (d) => setSummary(d.summary?.trim() || "요약할 최근 뉴스가 없어요."),
    onError: (e) => toast.push((e as Error).message, "danger"),
  });

  async function runCollect(kw: string[]) {
    if (runningRef.current) return;
    runningRef.current = true;
    setProg({ running: true, steps: [], total: 0 });
    try {
      await streamCollect({ keywords: kw, do_enrich: true }, (e: CollectEvent) => {
        if (e.type === "step") {
          const label = sourceMeta(e.source).label + (e.keyword ? ` · ${e.keyword}` : "");
          setProg((p) => (p ? { ...p, steps: [...p.steps, { label, found: e.found ?? 0 }], total: p.total + (e.found ?? 0) } : p));
        } else if (e.type === "done") {
          setProg((p) => (p ? { ...p, running: false, done: { articles: e.total_articles ?? 0, files: e.total_files ?? 0, saved: e.saved ?? [], errors: e.errors ?? [] } } : p));
          toast.push(`✅ ${e.total_articles ?? 0}건 수집했어요`, "success");
          qc.invalidateQueries({ queryKey: ["news"] });
          qc.invalidateQueries({ queryKey: ["collect"] });
        } else if (e.type === "error") {
          setProg((p) => (p ? { ...p, running: false, error: e.error } : p));
          toast.push(`⚠️ 수집 실패: ${e.error}`, "danger");
        }
      });
    } catch (err) {
      setProg((p) => (p ? { ...p, running: false, error: (err as Error).message } : p));
      toast.push(`⚠️ 수집 실패: ${(err as Error).message}`, "danger");
    } finally {
      runningRef.current = false;
    }
  }

  const activeSources = new Set(all.map((a) => articleChannel(a).label)).size;
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
        <button className="btn" disabled={summarize.isPending} onClick={() => summarize.mutate()}>
          {summarize.isPending ? "요약 중…" : "📰 최근 뉴스 요약"}</button>
        <CollectButton pending={running} onRun={() => runCollect([])} />
      </div>

      {view === "browse" ? (
        <BrowseView cat={cat} setCat={(c) => { setCat(c); setChan("전체"); }}
          channels={channels} chan={chan} setChan={setChan} items={items} q={query} onOpen={setOpen}
          loading={news.isLoading} />
      ) : (
        <SettingsView onCollect={(kw) => runCollect(kw)} collecting={running} />
      )}

      <ArticleModal article={open} onClose={() => setOpen(null)} />
      <CollectProgressModal prog={prog} onClose={() => { if (!running) setProg(null); }} />
      {summary !== null && (
        <Modal open onClose={() => setSummary(null)} title="📰 최근 뉴스 요약 (3일)" width={600}>
          <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: "var(--fs-body)" }}>{summary}</div>
        </Modal>
      )}
    </div>
  );
}

interface CollectProgress {
  running: boolean;
  steps: { label: string; found: number }[];
  total: number;
  done?: { articles: number; files: number; saved: CollectSaved[]; errors: CollectErr[] };
  error?: string;
}

function CollectProgressModal({ prog, onClose }: { prog: CollectProgress | null; onClose: () => void }) {
  if (!prog) return null;
  const last = prog.steps[prog.steps.length - 1];
  return (
    <Modal open onClose={onClose} title="뉴스 수집" width={460}>
      {prog.running ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span className="cl-spinner" aria-hidden />
            <span>수집 중… <b>{prog.total}</b>건 발견</span>
          </div>
          <div className="muted" style={{ fontSize: "var(--fs-caption)", minHeight: 18 }}>
            {last ? `${last.label} — ${last.found}건` : "출처에 연결하는 중…"}
          </div>
        </>
      ) : prog.error ? (
        <div style={{ color: "var(--semantic-danger)", lineHeight: 1.6 }}>⚠️ 수집 실패: {prog.error}</div>
      ) : prog.done ? (
        <div style={{ lineHeight: 1.7 }}>
          <div style={{ fontSize: "var(--fs-headline)", marginBottom: 6 }}>✅ {prog.done.articles}건 수집 완료</div>
          <div className="muted" style={{ fontSize: "var(--fs-caption)", marginBottom: 8 }}>
            파일 {prog.done.files}개 저장{prog.done.errors.length > 0 ? ` · 오류 ${prog.done.errors.length}건` : ""}
          </div>
          {prog.done.saved.length > 0 && (
            <div className="cl-done-srcs">
              {prog.done.saved.flatMap((s) =>
                s.sites && Object.keys(s.sites).length
                  ? Object.entries(s.sites).map(([site, n]) => ({ label: site, n }))
                  : [{ label: sourceMeta(s.source).label, n: s.count }],
              ).map((row, i) => (
                <div key={i} className="cl-done-src">
                  <span>{row.label}</span><b>{row.n}건</b>
                </div>
              ))}
            </div>
          )}
          {prog.done.errors.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary className="muted" style={{ fontSize: "var(--fs-caption)", cursor: "pointer" }}>오류 {prog.done.errors.length}건 보기</summary>
              <div style={{ marginTop: 6, maxHeight: 120, overflowY: "auto", display: "grid", gap: 4 }}>
                {prog.done.errors.slice(0, 8).map((er, i) => (
                  <div key={i} className="muted" style={{ fontSize: "var(--fs-micro)", lineHeight: 1.4 }}>
                    <b>{er.source ?? ""}{er.keyword ? `·${er.keyword}` : ""}</b> — {er.error}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      ) : null}
      {prog.steps.length > 0 && (
        <div style={{ marginTop: 12, maxHeight: 160, overflowY: "auto", display: "grid", gap: 4 }}>
          {prog.steps.slice(-12).map((s, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-caption)" }}>
              <span>{s.label}</span><span className="muted">{s.found}건</span>
            </div>
          ))}
        </div>
      )}
      {!prog.running && (
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button className="btn primary" onClick={onClose}>닫기</button>
        </div>
      )}
    </Modal>
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
  const [mode, setMode] = useState<"card" | "table">("card");
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Tabs items={[{ key: "keyword", label: "🔑 키워드 뉴스" }, { key: "portal", label: "🏛 뉴스 포탈" }]}
          value={cat} onChange={(c) => setCat(c as "keyword" | "portal")} />
        <span style={{ flex: 1 }} />
        <Tabs items={[{ key: "card", label: "🃏 카드" }, { key: "table", label: "📋 데이터 표" }]}
          value={mode} onChange={(m) => setMode(m as "card" | "table")} />
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
      {q && <div className="muted" style={{ marginBottom: 8 }}>검색: "{q}" — {items.length}건</div>}
      {loading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
        : items.length === 0 ? <EmptyState icon="🗞" title="기사가 없어요" hint="‘지금 수집’으로 수집을 시작하세요." />
        : mode === "table" ? <NewsTable items={items} onOpen={onOpen} />
        : <div className="bd-grid">{items.slice(0, 48).map((a) => (
            <div key={a.link} onClick={(e) => { e.preventDefault(); onOpen(a); }}><NewsCard article={a} /></div>
          ))}</div>}
    </>
  );
}

function NewsTable({ items, onOpen }: { items: NewsArticle[]; onOpen: (a: NewsArticle) => void }) {
  return (
    <div className="cl-table-wrap">
      <table className="cl-table">
        <thead><tr><th>출처</th><th>제목</th><th>요약</th><th>키워드</th><th>수집</th></tr></thead>
        <tbody>
          {items.slice(0, 200).map((a) => {
            const m = articleChannel(a);
            return (
              <tr key={a.link} onClick={() => onOpen(a)} style={{ cursor: "pointer" }}>
                <td><span className="cl-chip-dot" style={{ background: m.color }} /> {m.label}</td>
                <td className="cl-td-title">{a.title}</td>
                <td className="cl-td-sum">{newsSummary(a)}</td>
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
  // 목록은 본문(content)을 빼고 주므로 모달 열릴 때 상세를 별도 조회.
  const detail = useQuery({
    queryKey: ["news", "detail", article?.link],
    queryFn: () => api.news.detail(article!.link),
    enabled: !!article?.link,
    staleTime: 5 * 60 * 1000,
  });
  if (!article) return null;
  const m = articleChannel(article);
  const full = detail.data ?? article;
  const summary = newsSummary(full);
  const body = (full.content || "").trim();
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
      {summary && (
        <div style={{ padding: "10px 12px", marginBottom: 12, borderLeft: "3px solid var(--accent-primary)",
          background: "var(--surface-soft)", borderRadius: 6, lineHeight: 1.55, fontSize: "var(--fs-body)" }}>
          {summary}
        </div>
      )}
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

interface RunEntry {
  ts?: string; trigger?: string; ok?: boolean;
  total_articles?: number; total_files?: number; errors?: unknown[];
}

function RunTimeline({ runs }: { runs: RunEntry[] }) {
  if (runs.length === 0) return <div className="muted" style={{ marginTop: 8, fontSize: "var(--fs-caption)" }}>아직 수집 런 기록이 없어요.</div>;
  return (
    <div className="cl-runs">
      {runs.map((r, i) => {
        const errs = (r.errors ?? []).length;
        return (
          <div className="cl-run" key={i}>
            <span className="cl-run-dot" style={{ background: r.ok ? "var(--semantic-success)" : "var(--semantic-warning)" }} />
            <span className="cl-run-time">{r.ts ? ageLabel(r.ts) : "—"}</span>
            <span className="cl-run-trigger">{r.trigger === "manual" ? "수동" : r.trigger === "cron" ? "자동" : (r.trigger ?? "")}</span>
            <span className="cl-run-stat">{r.total_articles ?? 0}건 · {r.total_files ?? 0}파일{errs > 0 ? ` · 오류 ${errs}` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}

function SettingsView({ onCollect, collecting }: { onCollect: (kw: string[]) => void; collecting: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(""); const [url, setUrl] = useState("");
  const [diagUrl, setDiagUrl] = useState(""); const [kw, setKw] = useState("");
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.sources.list() });
  const srcHealth = useQuery({ queryKey: ["sources", "health"], queryFn: () => api.sources.health(7) });
  const hmap = new Map((srcHealth.data ?? []).map((h) => [h.name, h] as const));
  const status = useQuery({ queryKey: ["collect", "status"], queryFn: () => api.collect.status() });
  const today = useQuery({ queryKey: ["news", "today"], queryFn: () => api.news.today() });
  const taskdefs = useQuery({ queryKey: ["taskdefs", ""], queryFn: () => api.taskdefs.list() });
  const llm = useQuery({ queryKey: ["assistant", "status"], queryFn: () => api.assistant.status() });
  const crate = useQuery({ queryKey: ["news", "content-rate"], queryFn: () => api.news.contentRate(7) });
  const health = [
    { label: "오늘 뉴스", ok: (today.data?.length ?? 0) > 0, val: `${today.data?.length ?? 0}건` },
    { label: "본문 확보율", ok: (crate.data?.pct ?? 0) >= 50, val: crate.data ? `${crate.data.pct}%` : "…" },
    { label: "정의된 작업", ok: (taskdefs.data?.length ?? 0) > 0, val: `${taskdefs.data?.length ?? 0}개` },
    { label: "활성 출처", ok: (sources.data?.items.filter((s) => s.enabled).length ?? 0) > 0, val: `${sources.data?.items.filter((s) => s.enabled).length ?? 0}개` },
    { label: "LLM", ok: !!llm.data?.configured, val: llm.data?.configured ? "Ready" : "키 미설정" },
  ];

  const toggle = useMutation({ mutationFn: (n: string) => api.sources.toggle(n), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const add = useMutation({ mutationFn: () => api.sources.add(name, url), onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); setName(""); setUrl(""); toast.push("출처 추가됨", "success"); }, onError: (e) => toast.push((e as Error).message, "danger") });
  const remove = useMutation({ mutationFn: (n: string) => api.sources.remove(n), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const diag = useMutation({ mutationFn: () => api.collect.diagnose(diagUrl) });

  const daily = (status.data?.daily ?? []) as (string | null)[];
  const bars = daily.map((s, i) => ({ label: String(i), value: s ? 1 : 0, title: s ?? "수집 없음", highlight: i === daily.length - 1 }));
  const runs = useQuery({ queryKey: ["collect", "runs"], queryFn: () => api.collect.runs(12) });

  return (
    <div>
      <div className="card">
        <div className="card-title">🩺 데이터 준비 상태</div>
        <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 0 }}>
          {health.map((h) => (
            <div className="kpi-card" key={h.label} style={{ borderLeft: `3px solid ${h.ok ? "var(--semantic-success)" : "var(--semantic-warning)"}` }}>
              <div className="kpi-label">{h.ok ? "✅" : "⚠️"} {h.label}</div>
              <div className="kpi-value" style={{ fontSize: "var(--fs-headline)" }}>{h.val}</div>
            </div>
          ))}
        </div>
      </div>

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
            {(() => {
              const h = hmap.get(s.name);
              if (!h) return null;
              const tone = h.status === "정상" ? "success" : h.status === "무수집" ? "warning" : "default";
              return <>
                <span className="muted" style={{ fontSize: "var(--fs-micro)", marginLeft: "auto" }}>
                  {h.count_7d}건/7일{h.last_collected ? ` · ${ageLabel(h.last_collected)}` : ""}
                </span>
                <Badge tone={tone}>{h.status}</Badge>
              </>;
            })()}
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
        <RunTimeline runs={(runs.data ?? []) as RunEntry[]} />
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
