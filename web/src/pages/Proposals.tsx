import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { KPIStatGrid, Tabs, EmptyState, LoadError } from "../components/ui";
import { KanbanBoard, KanbanColumn } from "../components/ui/Kanban";
import { useToast } from "../components/ui/toast";
import { ageLabel } from "../lib/time";
import type { ProposalEntity } from "../api/types";

export default function Proposals() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState<"gen" | "archive">("gen");
  // 핸드오프로 들어오면 자동으로 제안 생성 탭.
  useEffect(() => { if (params.get("from")) setTab("gen"); }, [params]);
  return (
    <div>
      <Tabs items={[{ key: "gen", label: "🤖 제안 생성" }, { key: "archive", label: "📦 보관함" }]}
        value={tab} onChange={(t) => setTab(t as "gen" | "archive")} />
      {tab === "gen" ? <Generate /> : <Archive />}
    </div>
  );
}

function Generate() {
  const toast = useToast();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const from = params.get("from");
  const hoDept = params.get("dept") ?? "";
  const hoLv3 = params.get("lv3") ?? "";
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState("");   // 현재 제안서 MD(생성/다듬기로 갱신)
  const [instr, setInstr] = useState("");    // 다듬기 지시
  // 근거 기사(Step 8) — 생성 응답의 links 기반 근거. 보관 시 meta 로 함께 저장.
  const [evidence, setEvidence] = useState<Record<string, unknown>[]>([]);
  const [injectedCases, setInjectedCases] = useState<Record<string, unknown>[]>([]);
  const [genMeta, setGenMeta] = useState<Record<string, unknown>>({});
  const taskdefs = useQuery({ queryKey: ["taskdefs", ""], queryFn: () => api.taskdefs.list() });

  // 핸드오프(dept/lv3)면 매칭되는 작업정의를 자동 선택.
  useEffect(() => {
    if (selected || !taskdefs.data || (!hoLv3 && !hoDept)) return;
    const m = taskdefs.data.find((t) =>
      (hoLv3 && (t.task?.includes(hoLv3) || (t.json?.process_name as string)?.includes(hoLv3) || t.process?.includes(hoLv3))) ||
      (hoDept && t.dept?.includes(hoDept)));
    if (m) setSelected(m.process_id);
  }, [taskdefs.data, hoLv3, hoDept, selected]);

  const HANDOFF_LABEL: Record<string, string> = {
    board: "📊 보드에서 인계됨", matrix: "🧭 매트릭스에서 인계됨", insights: "🔎 인사이트에서 인계됨", brief: "📊 보드 브리핑에서 인계됨",
  };

  const gen = useMutation({
    mutationFn: async (pid: string) => {
      const t = await api.taskdefs.get(pid);
      return api.proposals.generate((t.json as Record<string, unknown>) ?? { process_id: pid });
    },
    onSuccess: (d, pid) => {
      setDraft(d.proposal);
      const ev = (d as unknown as { evidence?: Record<string, unknown>[] }).evidence ?? [];
      const cs = (d as unknown as { cases?: Record<string, unknown>[] }).cases ?? [];
      setEvidence(ev);
      setInjectedCases(cs);
      setGenMeta({
        task_id: pid,
        article_ids: ev.map((e) => e.article_id).filter(Boolean),
        matching_version: (d as unknown as { matching_version?: number }).matching_version,
        prompt_version: (d as unknown as { prompt_version?: number }).prompt_version,
      });
    },
  });
  // 다듬기 — 현재 draft + 지시 → 새 draft (처음부터 재생성 없이 반복 개선).
  const refine = useMutation({
    mutationFn: (instruction: string) => api.proposals.refine(draft, instruction),
    onSuccess: (d) => { setDraft(d.proposal); setInstr(""); toast.push("✨ 제안서를 다듬었어요", "success"); },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });
  const save = useMutation({
    // Proposal 엔터티로 저장(Step 13) — 근거 관계·버전을 구조 필드로 보존.
    mutationFn: (text: string) => api.proposals.save({
      title: text.split("\n")[0].replace(/^#+\s*/, "").slice(0, 60) || "제안서",
      content: text,
      task_id: String(genMeta.task_id ?? ""),
      article_ids: (genMeta.article_ids as string[]) ?? [],
      case_ids: injectedCases.map((c) => String(c.case_id ?? "")).filter(Boolean),
      matching_version: Number(genMeta.matching_version ?? 0),
      prompt_version: Number(genMeta.prompt_version ?? 0),
      status: "draft",
    }),
    onSuccess: () => { toast.push("📦 과제 보관함에 저장했어요 (초안)", "success"); qc.invalidateQueries({ queryKey: ["proposals"] }); },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });

  return (
    <>
      {from && (
        <div className="cl-alert" style={{ background: "var(--accent-ring)", color: "var(--accent-primary)", border: "1px solid var(--accent-ring)" }}>
          {HANDOFF_LABEL[from] ?? "인계됨"}{(hoDept || hoLv3) && ` — ${hoDept}${hoLv3 ? ` · ${hoLv3}` : ""}`}
          <span className="muted" style={{ marginLeft: "auto" }}>
            {(hoLv3 || hoDept) ? "매칭 작업 자동 선택 · " : ""}✓ 오른쪽 SOLA가 자동 검토를 시작했어요
          </span>
        </div>
      )}
      <div className="card">
        <div className="card-title">작업 선택 → 제안서 생성</div>
        <div className="pr-gen">
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">작업 정의 선택…</option>
            {taskdefs.data?.map((t) => <option key={t.process_id} value={t.process_id}>{t.process_id} — {(t.json?.process_name as string) || t.task || t.dept}</option>)}
          </select>
          <button className="btn primary" disabled={!selected || gen.isPending} onClick={() => gen.mutate(selected)}>
            {gen.isPending ? "생성 중…" : "제안서 생성"}</button>
        </div>
        {draft && <>
          {evidence.length > 0 && (
            <div className="card" style={{ margin: "10px 0", background: "var(--bg-subtle, transparent)" }}>
              <div className="card-title">📎 근거 기사 {evidence.length}건 <span className="muted" style={{ fontWeight: 400 }}>· 이 기사들만 제안 근거로 주입됨</span></div>
              {evidence.map((ev, i) => (
                <div key={String(ev.link ?? i)} style={{ fontSize: "var(--fs-caption)", lineHeight: 1.6, marginBottom: 6 }}>
                  <a href={String(ev.link ?? "#")} target="_blank" rel="noreferrer noopener">
                    [근거 {i + 1}] {String(ev.title ?? "")}</a>
                  <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>{String(ev.reason ?? "")}</div>
                </div>
              ))}
            </div>
          )}
          {injectedCases.length > 0 && (
            <div className="muted" style={{ fontSize: "var(--fs-caption)", margin: "4px 0" }}>
              📚 승인 사례 {injectedCases.length}건이 함께 주입됨: {injectedCases.map((c) => String(c.title ?? "")).join(" · ")}
            </div>
          )}
          {evidence.length === 0 && (
            <div className="muted" style={{ fontSize: "var(--fs-caption)", margin: "8px 0" }}>
              ⚠️ 이 작업과 매칭된 근거 기사가 없어요 — 제안서가 일반론일 수 있습니다. 수집을 늘리거나 작업정의 키워드를 보강하세요.
            </div>
          )}
          <div className="pr-output">{draft}</div>
          <div className="pr-refine" style={{ display: "flex", gap: 6, marginTop: 10 }}>
            <input style={{ flex: 1 }} value={instr} onChange={(e) => setInstr(e.target.value)}
              placeholder="다듬기 지시 예: 리스크 섹션 강화 · 더 짧게 · 보수적 톤으로"
              onKeyDown={(e) => { if (e.key === "Enter" && instr.trim() && !refine.isPending) refine.mutate(instr.trim()); }} />
            <button className="btn" disabled={!instr.trim() || refine.isPending} onClick={() => refine.mutate(instr.trim())}>
              {refine.isPending ? "다듬는 중…" : "✨ 다듬기"}</button>
          </div>
          <button className="btn primary" style={{ marginTop: 10 }} disabled={save.isPending} onClick={() => save.mutate(draft)}>
            📦 보관함에 저장</button>
        </>}
        {gen.error && <div style={{ color: "var(--semantic-danger)", marginTop: 8 }}>{(gen.error as Error).message}</div>}
      </div>
      <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>
        💡 오른쪽 SOLA 채팅으로 대화하며 다듬은 뒤 보관함에 저장할 수도 있어요.
      </div>
    </>
  );
}

// 9-상태 라이프사이클(§15) — 칸반은 4개 그룹으로 묶어 "가볍게 보기" 유지.
const STATUS_LABEL: Record<string, string> = {
  idea: "아이디어", draft: "초안", reviewing: "검토 중",
  feasibility: "타당성 평가", poc_ready: "PoC 준비", poc_running: "PoC 진행",
  adopted: "채택", on_hold: "보류", rejected: "기각",
};
const COLS: { title: string; statuses: string[]; dot: string; desc: string }[] = [
  { title: "제안", statuses: ["idea", "draft"], dot: "#64748B", desc: "아이디어·초안" },
  { title: "검토·평가", statuses: ["reviewing", "feasibility"], dot: "#0369A1", desc: "검토 중·타당성" },
  { title: "PoC", statuses: ["poc_ready", "poc_running"], dot: "#7C3AED", desc: "준비·진행" },
  { title: "결정", statuses: ["adopted", "on_hold", "rejected"], dot: "#15803D", desc: "채택·보류·기각" },
];

function Archive() {
  const qc = useQueryClient();
  const toast = useToast();
  const all = useQuery({ queryKey: ["proposals", "entities"], queryFn: () => api.proposals.listEntities() });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["proposals"] });
  };
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.proposals.setStatus(id, status),
    onSuccess: (_d, v) => { invalidate(); toast.push(`상태를 '${STATUS_LABEL[v.status] ?? v.status}'(으)로 옮겼어요`, "success"); },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.proposals.removeEntity(id),
    onSuccess: () => { invalidate(); toast.push("🗑 삭제했어요", "default"); },
    onError: (e) => toast.push(`삭제 실패: ${(e as Error).message}`, "danger"),
  });
  // 구 bookmark 보관함 → 엔터티 이관 (명시적 버튼 · 원본 보존 · 멱등).
  const migrate = useMutation({
    mutationFn: () => api.proposals.migrateBookmarks(),
    onSuccess: (r) => { invalidate(); toast.push(`구 보관함 이관 완료 — ${r.migrated}건 이관 · ${r.skipped}건 이미 존재`, "success"); },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });

  const items = all.data ?? [];
  const inStatuses = (ss: string[]) => items.filter((p) => ss.includes(p.status));
  const count = (s: string) => items.filter((p) => p.status === s).length;
  const decided = count("adopted") + count("rejected");
  const adoptedRate = decided ? Math.round((count("adopted") / decided) * 100) : 0;

  if (all.isLoading) return <div className="muted">불러오는 중…</div>;
  if (all.isError) return <LoadError message="과제를 불러오지 못했어요" onRetry={() => all.refetch()} />;

  const migrateBtn = (
    <button className="btn" disabled={migrate.isPending} onClick={() => migrate.mutate()}>
      {migrate.isPending ? "이관 중…" : "📥 구 보관함 이관"}</button>
  );

  if (items.length === 0) {
    return (
      <>
        <EmptyState icon="📦" title="아직 저장된 과제가 없어요"
          hint="'제안 생성' 탭에서 만들어 저장하거나, 예전 보관함(bookmark)의 제안서를 이관하세요." />
        <div style={{ textAlign: "center", marginTop: 8 }}>{migrateBtn}</div>
      </>
    );
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <KPIStatGrid cols={4} items={[
            { label: "총 과제", value: items.length },
            { label: "검토 중", value: count("reviewing") + count("feasibility"), tone: "warning" },
            { label: "PoC", value: count("poc_ready") + count("poc_running") },
            { label: "채택률(결정 대비)", value: `${adoptedRate}%`, tone: "success" },
          ]} />
        </div>
        {migrateBtn}
      </div>
      <KanbanBoard>
        {COLS.map((c) => {
          const cards = inStatuses(c.statuses);
          return (
            <KanbanColumn key={c.title} title={c.title} count={cards.length} dot={c.dot} desc={c.desc}>
              {cards.map((p) => <ProposalCard key={p.proposal_id} p={p}
                onStatus={(st) => setStatus.mutate({ id: p.proposal_id, status: st })}
                onRemove={() => confirm("삭제? (전환 이력도 함께 삭제됩니다)") && remove.mutate(p.proposal_id)} />)}
              {cards.length === 0 && <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>없음</div>}
            </KanbanColumn>
          );
        })}
      </KanbanBoard>
    </>
  );
}

function ProposalCard({ p, onStatus, onRemove }:
  { p: ProposalEntity; onStatus: (st: string) => void; onRemove: () => void }) {
  return (
    <div className="oa-card">
      <div className="oa-card-t">
        {p.title}
        {p.legacy && <span className="muted" style={{ fontSize: "var(--fs-micro)", marginLeft: 6 }} title="구 보관함에서 이관됨">🏷 이관</span>}
        {p.evidence_unavailable && <span style={{ fontSize: "var(--fs-micro)", marginLeft: 6, color: "var(--semantic-warning, #B45309)" }} title="이관 당시 근거 기사 관계가 저장되지 않아 복원 불가">⚠ 근거 없음</span>}
      </div>
      {p.content && <div className="oa-card-d">{p.content}</div>}
      {p.article_ids.length > 0 && (
        <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>📎 근거 {p.article_ids.length}건{p.case_ids.length > 0 && ` · 📚 사례 ${p.case_ids.length}건`}</div>
      )}
      <div className="oa-card-foot">
        <span className="oa-card-age">{ageLabel(p.created_at)}</span>
        <span className="oa-card-btns" style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
          <select value={p.status} onChange={(e) => onStatus(e.target.value)}
            style={{ fontSize: "var(--fs-micro)", padding: "2px 4px" }} title="상태 전환 (이력 보존)">
            {Object.entries(STATUS_LABEL).map(([st, label]) => <option key={st} value={st}>{label}</option>)}
          </select>
          <button className="oa-mini" onClick={onRemove}>🗑</button>
        </span>
      </div>
    </div>
  );
}
