import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { IngestResult } from "../api/types";

// 작업 정의 — 엑셀 업로드 + 목록/검색.
export default function TaskDefs() {
  const [q, setQ] = useState("");
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const list = useQuery({
    queryKey: ["taskdefs", q],
    queryFn: () => api.taskdefs.list(q ? { q } : undefined),
  });

  const upload = useMutation<IngestResult, Error, { file: File; replace: boolean }>({
    mutationFn: ({ file, replace }) => api.taskdefs.upload(file, replace),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["taskdefs"] }),
  });

  function onPick(replace: boolean) {
    const file = fileRef.current?.files?.[0];
    if (file) upload.mutate({ file, replace });
  }

  return (
    <div>
      <h1 className="page-title">📋 작업 정의</h1>

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
        <div className="card" key={t.process_id}>
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
