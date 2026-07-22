import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, streamCollect } from "../api/client";
import type { CollectEvent, CollectSaved, CollectErr } from "../api/client";
import { Modal, Badge } from "../components/ui";
import { useToast } from "../components/ui/toast";
import BarChart from "../components/charts/BarChart";
import { sourceMeta } from "../lib/news";
import { ageLabel } from "../lib/time";

// 수집 관리 (Step 11 — 운영 전용). 뉴스 읽기는 /feed(뉴스 탐색)로 분리됐다.
export default function Collect() {
  const qc = useQueryClient();
  const toast = useToast();

  const [prog, setProg] = useState<CollectProgress | null>(null);
  const [logOpen, setLogOpen] = useState(false);
  const [logRunId, setLogRunId] = useState<string | undefined>(undefined);  // 최근 런 우선 선택
  const running = !!prog?.running;
  const runningRef = useRef(false);

  async function runCollect(kw: string[]) {
    if (runningRef.current) return;
    runningRef.current = true;
    setProg({ running: true, steps: [], total: 0 });
    try {
      await streamCollect({ keywords: kw, do_enrich: true }, (e: CollectEvent) => {
        if (e.type === "step") {
          const label = sourceMeta(e.source).label + (e.keyword ? ` · ${e.keyword}` : "");
          setProg((p) => (p ? { ...p, steps: [...p.steps, { label, found: e.found ?? 0 }], total: p.total + (e.found ?? 0) } : p));
        } else if (e.type === "enrich") {
          setProg((p) => (p ? { ...p, enrich: { done: e.done ?? 0, total: e.total ?? 0 } } : p));
        } else if (e.type === "done") {
          setProg((p) => (p ? { ...p, running: false, done: { articles: e.total_articles ?? 0, files: e.total_files ?? 0, saved: e.saved ?? [], errors: e.errors ?? [] } } : p));
          if (e.run_id) setLogRunId(e.run_id);   // 방금 런 로그를 바로 열 수 있게
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

  return (
    <div>
      <div className="cl-bar">
        <span className="muted" style={{ fontSize: "var(--fs-caption)" }}>
          기사 읽기는 <b>뉴스 탐색</b> 메뉴에서 — 여기는 수집 실행·출처·진단만 다룹니다.
        </span>
        <span className="cl-grow" />
        <button className="btn" onClick={() => setLogOpen(true)} title="최근 수집 런의 상세 로그를 보고 복사합니다">📋 수집 로그</button>
        <CollectButton pending={running} onRun={() => runCollect([])} />
      </div>
      <SettingsView onCollect={(kw) => runCollect(kw)} collecting={running} />
      <CollectProgressModal prog={prog} onClose={() => { if (!running) setProg(null); }} />
      {logOpen && <CollectLogModal initialRunId={logRunId} onClose={() => setLogOpen(false)} />}
    </div>
  );
}

// 수집 로그 모달 — 최근 런 선택 + 상세 로그(단계별 소요·기사별 본문/이미지 확보) + 복사.
function CollectLogModal({ initialRunId, onClose }: { initialRunId?: string; onClose: () => void }) {
  const toast = useToast();
  const [sel, setSel] = useState<string | undefined>(initialRunId);
  const runs = useQuery({ queryKey: ["collect", "logs"], queryFn: () => api.collect.logs(20) });
  const list = runs.data ?? [];
  const runId = sel ?? initialRunId ?? list[0]?.run_id;
  const detail = useQuery({
    queryKey: ["collect", "log", runId],
    queryFn: () => api.collect.logDetail(runId as string),
    enabled: !!runId,
  });

  const copy = async () => {
    const text = detail.data?.text ?? "";
    try {
      await navigator.clipboard.writeText(text);
      toast.push("📄 로그를 복사했어요 — 채팅에 붙여넣어 주세요", "success");
    } catch {
      toast.push("복사 실패 — 로그 영역을 직접 선택해 복사하세요", "danger");
    }
  };

  return (
    <Modal open onClose={onClose} title="수집 로그" width={720}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <select value={runId ?? ""} onChange={(e) => setSel(e.target.value)} style={{ flex: 1, minWidth: 220 }}>
          {list.length === 0 && <option value="">최근 수집 런이 없어요</option>}
          {list.map((r) => {
            const ts = String((r.meta as Record<string, unknown>)?.ts ?? "").replace("T", " ").slice(0, 19);
            const dur = (r.meta as Record<string, unknown>)?.duration_s;
            return <option key={r.run_id} value={r.run_id}>{ts || r.run_id}{dur != null ? ` · ${dur}s` : ""} · {r.event_count}개 이벤트</option>;
          })}
        </select>
        <button className="btn primary" disabled={!detail.data?.text} onClick={copy}>📄 전체 복사</button>
      </div>
      {detail.isLoading && <div className="muted">불러오는 중…</div>}
      {detail.isError && <div style={{ color: "var(--semantic-danger)" }}>로그를 불러올 수 없어요(휘발됐거나 오래된 런).</div>}
      {detail.data && (
        <textarea readOnly value={detail.data.text}
          style={{ width: "100%", height: 380, fontFamily: "var(--font-mono, monospace)", fontSize: "var(--fs-micro, 12px)",
                   lineHeight: 1.5, whiteSpace: "pre", overflow: "auto", resize: "vertical",
                   border: "1px solid var(--line)", borderRadius: 8, padding: 10,
                   background: "var(--bg-subtle, var(--surface))", color: "var(--ink)" }} />
      )}
      <div className="muted" style={{ fontSize: "var(--fs-micro)", marginTop: 8 }}>
        ⚠ 로그는 서버 파일이라 재배포·슬립 시 사라져요 — 수집 직후 복사해 두세요. 최근 20런만 보관.
      </div>
    </Modal>
  );
}

interface CollectProgress {
  running: boolean;
  steps: { label: string; found: number }[];
  total: number;
  enrich?: { done: number; total: number };   // 본문 정리 진행(검색 후 가장 긴 단계)
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
            <span>
              {prog.enrich
                ? <>본문 정리 중… <b>{prog.enrich.done}</b>/{prog.enrich.total}건</>
                : <>기사 검색 중… <b>{prog.total}</b>건 발견</>}
            </span>
          </div>
          {prog.enrich && prog.enrich.total > 0 && (
            <div style={{ height: 6, borderRadius: 3, background: "var(--line)", overflow: "hidden", margin: "0 0 8px" }}>
              <div style={{ height: "100%", width: `${Math.min(100, Math.round((prog.enrich.done / prog.enrich.total) * 100))}%`,
                            background: "var(--accent-primary, #0E7C97)", transition: "width .3s" }} />
            </div>
          )}
          <div className="muted" style={{ fontSize: "var(--fs-caption)", minHeight: 18 }}>
            {prog.enrich
              ? "각 기사 본문·대표 이미지를 가져오는 중이에요 (가장 오래 걸리는 단계)"
              : last ? `${last.label} — ${last.found}건` : "출처에 연결하는 중…"}
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
    { label: "LLM", ok: !!llm.data?.configured, val: llm.data?.configured ? "정상" : "키 미설정" },
  ];

  const toggle = useMutation({ mutationFn: (n: string) => api.sources.toggle(n), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }), onError: (e) => toast.push(`출처 전환 실패: ${(e as Error).message}`, "danger") });
  const add = useMutation({ mutationFn: () => api.sources.add(name, url), onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); setName(""); setUrl(""); toast.push("출처 추가됨", "success"); }, onError: (e) => toast.push((e as Error).message, "danger") });
  const remove = useMutation({ mutationFn: (n: string) => api.sources.remove(n), onSuccess: () => { qc.invalidateQueries({ queryKey: ["sources"] }); toast.push("🗑 출처를 제거했어요", "default"); }, onError: (e) => toast.push(`제거 실패: ${(e as Error).message}`, "danger") });
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
        <div className="muted" style={{ fontSize: "var(--fs-micro)", marginTop: 6 }}>
          비워 두고 수집하면 <b>내 페르소나 관심 키워드</b>로 모아요 (없으면 조선·자동화 기본 키워드).
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
        {diag.data && <DiagResult d={diag.data as unknown as DiagReport} />}
        {diag.error && <div style={{ color: "var(--semantic-danger)", marginTop: 8 }}>{(diag.error as Error).message}</div>}
      </div>
    </div>
  );
}

interface DiagStep { name: string; label: string; status: number | null; length: number; ok: boolean; skipped: boolean; error: string | null; }
interface DiagReport {
  url: string; curl_cffi_available: boolean; fetched: boolean; all_blocked: boolean;
  soft_block_suspect: boolean; soft_block_reasons: string[];
  steps: DiagStep[];
  meta_images: { selector: string; url: string; junk: boolean }[];
  body_images: { selector: string; url: string; junk: boolean }[];
  content_selector: { selector: string; length: number; preview: string } | null;
  structured: { ldjson_len: number; fusion_len: number };
  final: { content_len: number; content_preview: string; image_url: string };
}

// 진단 결과 — raw JSON 대신 단계별 구조화 리포트(Streamlit _render_diag_result 이식).
function DiagResult({ d }: { d: DiagReport }) {
  const headTone = d.all_blocked ? "danger" : d.soft_block_suspect ? "warning" : d.fetched ? "success" : "default";
  const headText = d.all_blocked ? "전부 차단(IP 대역 의심)" : d.soft_block_suspect ? "200 위장 차단 의심" : d.fetched ? "HTML 확보" : "미확보";
  const imgs = [...(d.meta_images ?? []), ...(d.body_images ?? [])];
  return (
    <div className="cl-diagr">
      <div className="cl-diagr-head">
        <Badge tone={headTone}>{headText}</Badge>
        {d.soft_block_reasons?.map((r, i) => <span key={i} className="muted" style={{ fontSize: "var(--fs-micro)" }}>· {r}</span>)}
      </div>
      <div className="cl-diagr-steps">
        {(d.steps ?? []).map((s) => (
          <div key={s.name} className="cl-diagr-step">
            <span>{s.ok ? "✅" : s.skipped ? "⏭" : "❌"}</span>
            <span className="cl-diagr-step-l">{s.label}</span>
            <span className="muted">{s.skipped ? "건너뜀" : `HTTP ${s.status ?? "-"} · ${s.length}자`}{s.error ? ` · ${s.error}` : ""}</span>
          </div>
        ))}
      </div>
      <div className="cl-diagr-grid">
        <div><span className="muted">본문 셀렉터</span> {d.content_selector ? `${d.content_selector.selector} (${d.content_selector.length}자)` : "미매칭"}</div>
        <div><span className="muted">최종 본문</span> {d.final?.content_len ?? 0}자</div>
        <div><span className="muted">구조화</span> ld+json {d.structured?.ldjson_len ?? 0} · fusion {d.structured?.fusion_len ?? 0}</div>
        <div><span className="muted">이미지 후보</span> {imgs.length}개{imgs.length ? ` (junk ${imgs.filter((x) => x.junk).length})` : ""}</div>
      </div>
      {d.final?.image_url && <div className="muted" style={{ fontSize: "var(--fs-micro)", wordBreak: "break-all" }}>🖼 {d.final.image_url}</div>}
      {d.final?.content_preview && <div className="cl-diagr-prev">{d.final.content_preview}</div>}
    </div>
  );
}
