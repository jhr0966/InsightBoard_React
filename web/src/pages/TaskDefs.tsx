import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { KPIStatGrid, EmptyState, Chip } from "../components/ui";
import { useToast } from "../components/ui/toast";
import { ageLabel } from "../lib/time";
import type { IngestResult } from "../api/types";

type Json = Record<string, any>;
const LIST_FIELDS = ["objectives", "overall_quality_risks", "automation_potential_areas",
  "key_check_points", "safety_notes", "main_equipment"] as const;
const SEC_LABEL: Record<string, string> = {
  objectives: "🎯 목표", overall_quality_risks: "⚠️ 품질 리스크",
  automation_potential_areas: "🤖 자동화 가능 영역", key_check_points: "✅ 주요 확인사항",
  safety_notes: "🦺 안전 주의", main_equipment: "🛠 주요 장비",
};

export default function TaskDefs() {
  const qc = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [viewId, setViewId] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null); // "" = 새 작업
  const fileRef = useRef<HTMLInputElement>(null);

  const list = useQuery({ queryKey: ["taskdefs", q], queryFn: () => api.taskdefs.list(q ? { q } : undefined) });
  const upload = useMutation<IngestResult, Error, { file: File; replace: boolean }>({
    mutationFn: ({ file, replace }) => api.taskdefs.upload(file, replace),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["taskdefs"] }); toast.push(`✅ ${r.row_count}행 적재`, "success"); },
    onError: (e) => toast.push(`⚠️ ${e.message}`, "danger"),
  });
  const onPick = (replace: boolean) => { const f = fileRef.current?.files?.[0]; if (f) upload.mutate({ file: f, replace }); };

  const defs = list.data ?? [];
  const depts = new Set(defs.map((d) => d.dept).filter(Boolean)).size;
  const lastUpd = defs.map((d) => d.updated_at).filter(Boolean).sort().reverse()[0];

  if (editId !== null) return <EditForm id={editId} onDone={() => { setEditId(null); qc.invalidateQueries({ queryKey: ["taskdefs"] }); }} />;
  if (viewId) return <DetailView id={viewId} onBack={() => setViewId(null)} onEdit={() => { setEditId(viewId); setViewId(null); }}
    onDeleted={() => { setViewId(null); qc.invalidateQueries({ queryKey: ["taskdefs"] }); }} />;

  return (
    <div>
      <KPIStatGrid cols={3} items={[
        { label: "등록 정의", value: list.isLoading ? "…" : defs.length },
        { label: "부서", value: depts },
        { label: "마지막 갱신", value: lastUpd ? ageLabel(lastUpd) : "—" },
      ]} />

      <div className="card">
        <div className="card-title">공정정의서 엑셀 업로드</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input ref={fileRef} type="file" accept=".xlsx,.xls" />
          <button className="btn" disabled={upload.isPending} onClick={() => onPick(false)}>추가</button>
          <button className="btn primary" disabled={upload.isPending} onClick={() => onPick(true)}>교체</button>
          <button className="btn" style={{ marginLeft: "auto" }} onClick={() => setEditId("")}>＋ 새 작업 정의</button>
        </div>
        {upload.data && <div style={{ marginTop: 8 }} className="muted">{upload.data.row_count}행 (생성 {upload.data.sqlite_created} · 갱신 {upload.data.sqlite_updated} · skip {upload.data.sqlite_skipped})</div>}
      </div>

      <input className="cl-search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="작업 정의 검색 (공정 ID·작업명·내용)" style={{ width: "100%", marginBottom: 16 }} />

      {list.isLoading ? <div className="td-list">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" style={{ height: 110 }} />)}</div>
        : defs.length === 0 ? <EmptyState icon="📋" title="작업 정의가 없어요" hint="엑셀을 업로드하거나 새로 추가하세요." />
        : <div className="td-list">{defs.map((t) => (
          <div className="td-card" key={t.process_id} onClick={() => setViewId(t.process_id)}>
            <div className="td-card-name">{(t.json?.process_name as string) || t.task || t.process_id}</div>
            <div className="td-card-meta">{t.team} · {t.dept}{t.division ? ` · ${t.division}` : ""}</div>
            <div className="td-card-pid">{t.process_id}</div>
          </div>
        ))}</div>}
    </div>
  );
}

function DetailView({ id, onBack, onEdit, onDeleted }: { id: string; onBack: () => void; onEdit: () => void; onDeleted: () => void }) {
  const toast = useToast();
  const [showHist, setShowHist] = useState(false);
  const t = useQuery({ queryKey: ["taskdef", id], queryFn: () => api.taskdefs.get(id) });
  const hist = useQuery({ queryKey: ["taskdef", id, "history"], queryFn: () => api.taskdefs.history(id), enabled: showHist });
  const del = useMutation({ mutationFn: () => api.taskdefs.remove(id), onSuccess: () => { toast.push(`🗑️ ${id} 삭제`, "default"); onDeleted(); } });

  if (t.isLoading) return <div className="muted">불러오는 중…</div>;
  const j = (t.data?.json ?? {}) as Json;
  const meta = (j.org_meta ?? {}) as Json;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <button className="btn" onClick={onBack}>← 목록</button>
        <button className="btn" onClick={() => setShowHist((s) => !s)}>🕒 이력</button>
        <button className="btn primary" style={{ marginLeft: "auto" }} onClick={onEdit}>✏️ 수정</button>
        <button className="btn" onClick={() => confirm(`삭제: ${id}?`) && del.mutate()}>🗑️ 삭제</button>
      </div>

      <div className="card">
        <div style={{ fontSize: "var(--fs-headline)", fontWeight: "var(--fw-bold)" }}>{(j.process_name as string) || id}</div>
        <div className="td-card-pid">{id}</div>
        <div className="td-meta-grid">
          {[["팀", meta.team], ["부서", meta.dept], ["분과", meta.division], ["공정", meta.process], ["작업", meta.task], ["세부", meta.sub_task]].map(([k, v]) =>
            v ? <div className="td-meta-cell" key={k}><span className="muted">{k}</span>{v}</div> : null)}
        </div>
        {j.process_description && <div style={{ marginTop: 8 }}>{j.process_description}</div>}

        {j.work_flow && <div className="td-sec"><div className="td-sec-h">🔄 작업 흐름</div><div style={{ whiteSpace: "pre-wrap", fontSize: "var(--fs-caption)" }}>{j.work_flow}</div></div>}
        {LIST_FIELDS.map((f) => Array.isArray(j[f]) && j[f].length > 0 ? (
          <div className="td-sec" key={f}><div className="td-sec-h">{SEC_LABEL[f]}</div>
            <ul>{(j[f] as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        ) : null)}
        {(j.previous_process || j.next_process) && (
          <div className="td-sec"><div className="td-sec-h">🔗 공정 연결</div>
            <div className="td-flow"><span>{j.previous_process || "—"}</span><span>→</span><span className="td-flow-now">{meta.process || id}</span><span>→</span><span>{j.next_process || "—"}</span></div>
          </div>
        )}
      </div>

      {showHist && (
        <div className="card">
          <div className="card-title">변경 이력</div>
          {hist.data?.length === 0 && <div className="muted">이력 없음</div>}
          {hist.data?.map((h) => (
            <div className="td-hist-row" key={h.id}>
              <Chip>{h.action}</Chip><span className="muted">{ageLabel(h.changed_at)}</span>
              <span className="muted">{h.source}</span><span>{h.changed_by ?? ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EditForm({ id, onDone }: { id: string; onDone: () => void }) {
  const toast = useToast();
  const isNew = id === "";
  const existing = useQuery({ queryKey: ["taskdef", id], queryFn: () => api.taskdefs.get(id), enabled: !isNew });
  const [f, setF] = useState<Json | null>(isNew ? blank() : null);
  const cur = f ?? (existing.data?.json as Json) ?? null;

  const save = useMutation({
    mutationFn: (json: Json) => api.taskdefs.upsert(String(json.process_id), { json }),
    onSuccess: (_d, json) => { toast.push(`✅ ${json.process_id} 저장`, "success"); onDone(); },
    onError: (e) => toast.push(`⚠️ ${(e as Error).message}`, "danger"),
  });

  if (!cur) return <div className="muted">불러오는 중…</div>;
  const meta = (cur.org_meta ?? {}) as Json;
  const set = (patch: Json) => setF({ ...cur, ...patch });
  const setMeta = (patch: Json) => setF({ ...cur, org_meta: { ...meta, ...patch } });
  const lines = (v: any) => (Array.isArray(v) ? v.join("\n") : "");
  const setList = (k: string, v: string) => set({ [k]: v.split("\n").map((s) => s.trim()).filter(Boolean) });

  function submit() {
    if (!cur.process_id || !meta.team || !meta.dept) { toast.push("공정 ID·팀·부서는 필수예요", "danger"); return; }
    save.mutate(cur);
  }

  const field = (label: string, value: string, on: (v: string) => void, full = false) => (
    <div className={`td-field${full ? " full" : ""}`}><label>{label}</label><input value={value || ""} onChange={(e) => on(e.target.value)} /></div>
  );
  const area = (k: string, label: string) => (
    <div className="td-field full"><label>{label} (한 줄에 하나)</label>
      <textarea rows={4} value={lines(cur[k])} onChange={(e) => setList(k, e.target.value)} /></div>
  );

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button className="btn" onClick={onDone}>← 취소</button>
        <button className="btn primary" style={{ marginLeft: "auto" }} disabled={save.isPending} onClick={submit}>{save.isPending ? "저장 중…" : "💾 저장"}</button>
      </div>
      <div className="card">
        <div className="card-title">{isNew ? "새 작업 정의" : `수정 — ${id}`}</div>
        <div className="td-form">
          {field("공정 ID *", cur.process_id, (v) => set({ process_id: v }))}
          {field("공정명", cur.process_name, (v) => set({ process_name: v }))}
          {field("팀 *", meta.team, (v) => setMeta({ team: v }))}
          {field("부서 *", meta.dept, (v) => setMeta({ dept: v }))}
          {field("분과", meta.division, (v) => setMeta({ division: v }))}
          {field("공정", meta.process, (v) => setMeta({ process: v }))}
          {field("작업", meta.task, (v) => setMeta({ task: v }))}
          {field("세부 작업", meta.sub_task, (v) => setMeta({ sub_task: v }))}
          <div className="td-field full"><label>공정 설명</label><textarea rows={2} value={cur.process_description || ""} onChange={(e) => set({ process_description: e.target.value })} /></div>
          <div className="td-field full"><label>작업 흐름</label><textarea rows={3} value={cur.work_flow || ""} onChange={(e) => set({ work_flow: e.target.value })} /></div>
          {area("objectives", "🎯 목표")}
          {area("key_check_points", "✅ 주요 확인사항")}
          {area("overall_quality_risks", "⚠️ 품질 리스크")}
          {area("automation_potential_areas", "🤖 자동화 가능 영역")}
          {area("safety_notes", "🦺 안전 주의")}
          {area("main_equipment", "🛠 주요 장비")}
          {field("이전 공정", cur.previous_process, (v) => set({ previous_process: v }))}
          {field("다음 공정", cur.next_process, (v) => set({ next_process: v }))}
        </div>
      </div>
    </div>
  );
}

function blank(): Json {
  return { process_id: "", process_name: "", org_meta: { team: "", dept: "", division: "", process: "", task: "", sub_task: "" }, objectives: [] };
}
