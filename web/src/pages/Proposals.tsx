import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// 자동화 제안 — 작업정의 선택 → 제안서 생성 + 채택 제안서 목록(북마크).
export default function Proposals() {
  const [selected, setSelected] = useState<string>("");
  const taskdefs = useQuery({ queryKey: ["taskdefs", ""], queryFn: () => api.taskdefs.list() });
  const saved = useQuery({ queryKey: ["bookmarks", "proposal"], queryFn: () => api.bookmarks.list("proposal") });

  const gen = useMutation({
    mutationFn: async (processId: string) => {
      const t = await api.taskdefs.get(processId);
      return api.proposals.generate((t.json as Record<string, unknown>) ?? { process_id: processId });
    },
  });

  return (
    <div>
      <h1 className="page-title">🤖 자동화 제안</h1>

      <div className="card">
        <strong>작업 선택 → 제안서 생성</strong>
        <div className="drawer-input" style={{ border: 0, padding: "10px 0 0" }}>
          <select value={selected} onChange={(e) => setSelected(e.target.value)} style={{ flex: 1 }}>
            <option value="">작업 정의 선택…</option>
            {taskdefs.data?.map((t) => (
              <option key={t.process_id} value={t.process_id}>
                {t.process_id} — {t.task ?? t.dept}
              </option>
            ))}
          </select>
          <button
            className="btn primary"
            disabled={!selected || gen.isPending}
            onClick={() => gen.mutate(selected)}
          >
            {gen.isPending ? "생성 중…" : "제안서 생성"}
          </button>
        </div>
        {gen.data && (
          <pre style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>{gen.data.proposal}</pre>
        )}
        {gen.error && <div style={{ color: "var(--semantic-danger)" }}>{(gen.error as Error).message}</div>}
      </div>

      <div className="card">
        <strong>보관된 제안서</strong>
        {saved.data?.length === 0 && <div className="muted">아직 없음</div>}
        {saved.data?.map((b) => (
          <div key={b.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--surface-divider)" }}>
            <span className="chip">{b.status}</span> {b.title}
          </div>
        ))}
      </div>
    </div>
  );
}
