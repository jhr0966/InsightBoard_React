import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { IngestResult } from "../api/types";
import { useToast } from "../components/ui/toast";

const NEW_TEMPLATE = JSON.stringify(
  {
    process_id: "NEW-001",
    org_meta: { team: "", dept: "", division: "", process: "", task: "" },
    objectives: [],
  },
  null,
  2,
);

// 작업 정의 — 엑셀 업로드 + 목록/검색 + JSON 편집(per-task CRUD).
export default function TaskDefs() {
  const [q, setQ] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const qc = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const list = useQuery({
    queryKey: ["taskdefs", q],
    queryFn: () => api.taskdefs.list(q ? { q } : undefined),
  });

  const upload = useMutation<IngestResult, Error, { file: File; replace: boolean }>({
    mutationFn: ({ file, replace }) => api.taskdefs.upload(file, replace),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["taskdefs"] }),
  });

  const save = useMutation<unknown, Error, { id: string; json: Record<string, unknown> }>({
    mutationFn: ({ id, json }) => api.taskdefs.upsert(id, { json }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["taskdefs"] });
      setEditId(null);
      toast.push(`✅ ${v.id} 작업 정의를 저장했어요`, "success");
    },
    onError: (e) => toast.push(`⚠️ 저장 실패: ${e.message}`, "danger"),
  });

  const remove = useMutation<unknown, Error, string>({
    mutationFn: (id) => api.taskdefs.remove(id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["taskdefs"] });
      setEditId(null);
      toast.push(`🗑️ ${id} 삭제했어요`, "default");
    },
  });

  function onPick(replace: boolean) {
    const file = fileRef.current?.files?.[0];
    if (file) upload.mutate({ file, replace });
  }

  async function openEditor(id: string) {
    const t = await api.taskdefs.get(id);
    setDraft(JSON.stringify(t.json ?? {}, null, 2));
    setEditId(id);
  }

  function newDef() {
    setDraft(NEW_TEMPLATE);
    setEditId("");
  }

  function onSave() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draft);
    } catch (e) {
      alert(`JSON 파싱 오류: ${(e as Error).message}`);
      return;
    }
    const id = String((parsed as { process_id?: unknown }).process_id ?? editId ?? "").trim();
    if (!id) {
      alert("process_id 가 필요합니다.");
      return;
    }
    save.mutate({ id, json: parsed });
  }

  return (
    <div>
      <div className="card">
        <strong>공정정의서 엑셀 업로드</strong>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
          <input ref={fileRef} type="file" accept=".xlsx,.xls" />
          <button className="btn" disabled={upload.isPending} onClick={() => onPick(false)}>
            추가 업로드
          </button>
          <button className="btn primary" disabled={upload.isPending} onClick={() => onPick(true)}>
            교체 업로드
          </button>
          <button className="btn" style={{ marginLeft: "auto" }} onClick={newDef}>
            + 새 작업 정의
          </button>
        </div>
        {upload.isPending && <div className="muted" style={{ marginTop: 8 }}>적재 중…</div>}
        {upload.data && (
          <div style={{ marginTop: 8 }}>
            ✅ {upload.data.row_count}행 적재 (생성 {upload.data.sqlite_created} · 갱신{" "}
            {upload.data.sqlite_updated} · skip {upload.data.sqlite_skipped})
          </div>
        )}
        {upload.error && (
          <div style={{ marginTop: 8, color: "var(--semantic-danger)" }}>{upload.error.message}</div>
        )}
      </div>

      {editId !== null && (
        <div className="card">
          <strong>{editId ? `편집: ${editId}` : "새 작업 정의"}</strong>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            style={{
              width: "100%", minHeight: 240, marginTop: 10, fontFamily: "var(--font-mono)",
              fontSize: "var(--fs-caption)", border: "1px solid var(--surface-divider)",
              borderRadius: "var(--r-md)", padding: "var(--space-3)",
            }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button className="btn primary" disabled={save.isPending} onClick={onSave}>
              {save.isPending ? "저장 중…" : "저장"}
            </button>
            {editId && (
              <button
                className="btn"
                disabled={remove.isPending}
                onClick={() => confirm(`삭제: ${editId}?`) && remove.mutate(editId)}
              >
                삭제
              </button>
            )}
            <button className="btn" onClick={() => setEditId(null)}>취소</button>
          </div>
          {save.error && (
            <div style={{ marginTop: 8, color: "var(--semantic-danger)" }}>{save.error.message}</div>
          )}
        </div>
      )}

      <div className="drawer-input" style={{ border: 0, padding: 0, marginBottom: 16 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="작업 정의 검색 (공정 ID·작업명·내용)"
        />
      </div>

      {list.isLoading && <div className="muted">불러오는 중…</div>}
      {list.error && <div style={{ color: "var(--semantic-danger)" }}>{(list.error as Error).message}</div>}
      {list.data?.length === 0 && <div className="muted">작업 정의가 없습니다.</div>}
      {list.data?.map((t) => (
        <div className="card" key={t.process_id} onClick={() => openEditor(t.process_id)} style={{ cursor: "pointer" }}>
          <div style={{ fontWeight: 600 }}>{t.process_id}</div>
          <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>
            {t.team} · {t.dept} {t.division ? `· ${t.division}` : ""}
          </div>
          {t.task && <div style={{ marginTop: 4 }}>{t.task}</div>}
        </div>
      ))}
    </div>
  );
}
