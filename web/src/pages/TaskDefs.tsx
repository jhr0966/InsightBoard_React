import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// 작업 정의 — 목록 + 검색.
export default function TaskDefs() {
  const [q, setQ] = useState("");
  const list = useQuery({
    queryKey: ["taskdefs", q],
    queryFn: () => api.taskdefs.list(q ? { q } : undefined),
  });

  return (
    <div>
      <h1 className="page-title">📋 작업 정의</h1>
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
