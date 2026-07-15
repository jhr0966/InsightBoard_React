import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { KPIStatGrid, Tabs, EmptyState } from "../components/ui";
import { KanbanBoard, KanbanColumn } from "../components/ui/Kanban";
import { useToast } from "../components/ui/toast";
import { ageLabel } from "../lib/time";
import type { Bookmark } from "../api/types";

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
    // 근거 관계(meta)를 본문과 함께 저장 — 나중에 "이 제안의 근거가 뭐였지"를 복원.
    mutationFn: (text: string) => api.bookmarks.create({
      type: "proposal", title: text.split("\n")[0].slice(0, 60) || "제안서", content: text,
      meta: genMeta,
    } as Parameters<typeof api.bookmarks.create>[0]),
    onSuccess: () => { toast.push("📦 보관함에 저장했어요 (검토 대기)", "success"); qc.invalidateQueries({ queryKey: ["bookmarks"] }); },
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

const COLS: { status: string; title: string; dot: string; desc: string }[] = [
  { status: "pending", title: "대기", dot: "#0369A1", desc: "검토 대기 중" },
  { status: "adopted", title: "채택", dot: "#15803D", desc: "의사결정 완료" },
  { status: "rejected", title: "기각", dot: "#B45309", desc: "사유와 함께 보관" },
];

function Archive() {
  const qc = useQueryClient();
  const toast = useToast();
  const all = useQuery({ queryKey: ["bookmarks", "proposal"], queryFn: () => api.bookmarks.list("proposal") });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.bookmarks.setStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bookmarks"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.bookmarks.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bookmarks"] }); toast.push("삭제됨", "default"); },
  });

  const items = all.data ?? [];
  const byStatus = (s: string) => items.filter((b) => b.status === s);
  const adoptedRate = items.length ? Math.round((byStatus("adopted").length / items.length) * 100) : 0;

  if (all.isLoading) return <div className="muted">불러오는 중…</div>;
  if (items.length === 0) return <EmptyState icon="📦" title="아직 제안서가 없어요" hint="‘제안 생성’ 탭에서 만들어 보관함에 저장하세요." />;

  const actionsFor = (b: Bookmark) => {
    if (b.status === "pending") return [["채택", "adopted"], ["기각", "rejected"]];
    return [["↶ 대기로", "pending"]];
  };

  return (
    <>
      <KPIStatGrid cols={4} items={[
        { label: "총 제안", value: items.length },
        { label: "채택", value: byStatus("adopted").length, tone: "success" },
        { label: "대기", value: byStatus("pending").length, tone: "warning" },
        { label: "채택률", value: `${adoptedRate}%` },
      ]} />
      <KanbanBoard>
        {COLS.map((c) => {
          const cards = byStatus(c.status);
          return (
            <KanbanColumn key={c.status} title={c.title} count={cards.length} dot={c.dot} desc={c.desc}>
              {cards.map((b) => (
                <div className="oa-card" key={b.id}>
                  <div className="oa-card-t">{b.title}</div>
                  {b.content && <div className="oa-card-d">{b.content}</div>}
                  <div className="oa-card-foot">
                    <span className="oa-card-age">{ageLabel(b.created_at)}</span>
                    <span className="oa-card-btns">
                      {actionsFor(b).map(([label, st]) => (
                        <button key={st} className="oa-mini" onClick={() => setStatus.mutate({ id: b.id, status: st })}>{label}</button>
                      ))}
                      <button className="oa-mini" onClick={() => confirm("삭제?") && remove.mutate(b.id)}>🗑</button>
                    </span>
                  </div>
                </div>
              ))}
              {cards.length === 0 && <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>없음</div>}
            </KanbanColumn>
          );
        })}
      </KanbanBoard>
    </>
  );
}
