import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { KPIStatGrid, EmptyState, Chip, Modal, LoadError } from "../components/ui";
import { useToast } from "../components/ui/toast";
import { ageLabel } from "../lib/time";
import type { IngestResult, UploadPreview } from "../api/types";

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

  const [preview, setPreview] = useState<{ diff: UploadPreview; file: File; replace: boolean } | null>(null);
  const [fileName, setFileName] = useState("");

  const list = useQuery({ queryKey: ["taskdefs", q], queryFn: () => api.taskdefs.list(q ? { q } : undefined) });
  const upload = useMutation<IngestResult, Error, { file: File; replace: boolean }>({
    mutationFn: ({ file, replace }) => api.taskdefs.upload(file, replace),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["taskdefs"] }); setPreview(null); toast.push(`✅ ${r.row_count}행 적재`, "success"); },
    onError: (e) => toast.push(`⚠️ ${e.message}`, "danger"),
  });
  // 업로드 전 미리보기(저장 X) → 모달에서 확인 후 실제 반영.
  const prev = useMutation<UploadPreview, Error, { file: File; replace: boolean }>({
    mutationFn: ({ file }) => api.taskdefs.uploadPreview(file),
    onSuccess: (diff, { file, replace }) => setPreview({ diff, file, replace }),
    onError: (e) => toast.push(`⚠️ ${e.message}`, "danger"),
  });
  const onPick = (replace: boolean) => { const f = fileRef.current?.files?.[0]; if (f) prev.mutate({ file: f, replace }); else toast.push("파일을 먼저 선택하세요", "warning"); };

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
          {/* 네이티브 file input 을 숨기고 스타일 라벨로 대체 — 다른 .btn 들과 시각 일관. */}
          <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }} id="td-file"
            onChange={(e) => setFileName(e.target.files?.[0]?.name ?? "")} />
          <label htmlFor="td-file" className="btn" style={{ cursor: "pointer" }}>📂 파일 선택</label>
          <span className="muted" style={{ fontSize: "var(--fs-caption)", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fileName || "선택된 파일 없음"}</span>
          <button className="btn" disabled={prev.isPending || upload.isPending} onClick={() => onPick(false)}>{prev.isPending ? "확인 중…" : "추가"}</button>
          <button className="btn primary" disabled={prev.isPending || upload.isPending} onClick={() => onPick(true)}>교체</button>
          <button className="btn" style={{ marginLeft: "auto" }} onClick={() => setEditId("")}>＋ 새 작업 정의</button>
        </div>
        <div className="muted" style={{ marginTop: 8, fontSize: "var(--fs-caption)" }}>업로드 전 변경 내역(신규·갱신·삭제)을 미리 확인합니다.</div>
        {upload.data && <div style={{ marginTop: 8 }} className="muted">{upload.data.row_count}행 (생성 {upload.data.sqlite_created} · 갱신 {upload.data.sqlite_updated} · skip {upload.data.sqlite_skipped})</div>}
      </div>

      {preview && <UploadPreviewModal info={preview} pending={upload.isPending}
        onConfirm={() => upload.mutate({ file: preview.file, replace: preview.replace })}
        onClose={() => setPreview(null)} />}

      <input className="cl-search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="작업 정의 검색 (공정 ID·작업명·내용)" style={{ width: "100%", marginBottom: 16 }} />

      {list.isLoading ? <div className="td-list">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" style={{ height: 110 }} />)}</div>
        : list.isError ? <LoadError message="작업 정의를 불러오지 못했어요" onRetry={() => list.refetch()} />
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
  const del = useMutation({
    mutationFn: () => api.taskdefs.remove(id),
    onSuccess: () => { toast.push(`🗑️ ${id} 삭제했어요`, "default"); onDeleted(); },
    onError: (e) => toast.push(`삭제 실패: ${(e as Error).message}`, "danger"),
  });

  if (t.isLoading) return <div className="muted">불러오는 중…</div>;
  if (t.isError) return <LoadError message="작업 정의를 불러오지 못했어요" onRetry={() => t.refetch()} />;
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

function UploadPreviewModal({ info, pending, onConfirm, onClose }: {
  info: { diff: UploadPreview; file: File; replace: boolean }; pending: boolean;
  onConfirm: () => void; onClose: () => void;
}) {
  const { diff, replace } = info;
  const c = diff.counts;
  const willRemove = replace && c.removed > 0;
  const group = (label: string, color: string, items: { process_id: string; name: string }[]) =>
    items.length === 0 ? null : (
      <div className="td-diff-grp">
        <div className="td-diff-h" style={{ color }}>{label} {items.length}</div>
        <div className="td-diff-list">
          {items.slice(0, 8).map((it) => <div key={it.process_id} className="td-diff-row"><b>{it.process_id}</b> {it.name}</div>)}
          {items.length > 8 && <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>+{items.length - 8}건 더</div>}
        </div>
      </div>
    );
  return (
    <Modal open onClose={onClose} title={`업로드 미리보기 — ${replace ? "교체" : "추가"}`} width={560}>
      <div className="muted" style={{ marginBottom: 10, fontSize: "var(--fs-caption)" }}>
        {diff.row_count}행 파싱됨 · 기존 {c.existing}건 · <b style={{ color: "var(--semantic-success)" }}>신규 {c.new}</b> · 갱신 {c.updated}{replace ? <> · <b style={{ color: "var(--semantic-danger)" }}>삭제 {c.removed}</b></> : ""}
      </div>
      {willRemove && (
        <div className="cl-alert" style={{ background: "var(--semantic-danger-soft, rgba(220,38,38,.1))", color: "var(--semantic-danger)", marginBottom: 10 }}>
          ⚠️ 교체 시 업로드에 없는 기존 작업정의 {c.removed}건이 <b>삭제</b>됩니다.
        </div>
      )}
      <div style={{ maxHeight: 280, overflowY: "auto" }}>
        {group("🟢 신규", "var(--semantic-success)", diff.new)}
        {group("🔵 갱신", "var(--accent-primary)", diff.updated)}
        {replace && group("🔴 삭제(교체 시)", "var(--semantic-danger)", diff.removed)}
        {c.new === 0 && c.updated === 0 && (!replace || c.removed === 0) &&
          <div className="muted">변경 사항이 없습니다(작업 정의로 적재되는 행 기준).</div>}
      </div>
      <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn" onClick={onClose} disabled={pending}>취소</button>
        <button className={`btn ${willRemove ? "" : "primary"}`} onClick={onConfirm} disabled={pending}
          style={willRemove ? { background: "var(--semantic-danger)", color: "#fff" } : undefined}>
          {pending ? "반영 중…" : replace ? "교체 실행" : "추가 실행"}
        </button>
      </div>
    </Modal>
  );
}

function EditForm({ id, onDone }: { id: string; onDone: () => void }) {
  const toast = useToast();
  const isNew = id === "";
  const existing = useQuery({ queryKey: ["taskdef", id], queryFn: () => api.taskdefs.get(id), enabled: !isNew });
  const [f, setF] = useState<Json | null>(isNew ? blank() : null);
  const [tdText, setTdText] = useState<string | null>(null);  // task_def_text(줄글 정의) — json 과 별도
  const cur = f ?? (existing.data?.json as Json) ?? null;
  const curText = tdText ?? existing.data?.task_def_text ?? "";

  const save = useMutation({
    mutationFn: (p: { json: Json; text: string }) =>
      api.taskdefs.upsert(String(p.json.process_id), { json: p.json, task_def_text: p.text }),
    onSuccess: (_d, p) => { toast.push(`✅ ${p.json.process_id} 저장`, "success"); onDone(); },
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
    save.mutate({ json: cur, text: curText });
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
          {field("도메인", cur.process_domain, (v) => set({ process_domain: v }))}
          {field("분류", cur.process_category, (v) => set({ process_category: v }))}
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
          <div className="td-field full"><label>줄글 정의</label>
            <textarea rows={3} value={curText} onChange={(e) => setTdText(e.target.value)}
              placeholder="공정정의서 원문(줄글). 매칭·제안에 함께 쓰입니다." /></div>
        </div>
      </div>
    </div>
  );
}

function blank(): Json {
  return { process_id: "", process_name: "", process_domain: "", process_category: "", org_meta: { team: "", dept: "", division: "", process: "", task: "", sub_task: "" }, objectives: [] };
}
