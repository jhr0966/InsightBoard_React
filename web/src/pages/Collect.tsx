import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

// 뉴스 수집 — 수집 실행 + 최근 기사 카드 목록.
export default function Collect() {
  const [days, setDays] = useState(7);
  const [kw, setKw] = useState("");
  const qc = useQueryClient();
  const news = useQuery({ queryKey: ["news", days], queryFn: () => api.news.list({ days, limit: 60 }) });

  const collect = useMutation({
    mutationFn: () =>
      api.collect.run(kw.split(",").map((s) => s.trim()).filter(Boolean), { do_enrich: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news"] }),
  });

  return (
    <div>
      <h1 className="page-title">🗞 뉴스 수집</h1>

      <div className="card">
        <strong>수집 실행</strong>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input
            style={{ flex: 1 }}
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            placeholder="키워드(쉼표 구분) 예: 용접 로봇, 디지털 트윈"
          />
          <button className="btn primary" disabled={collect.isPending || !kw.trim()} onClick={() => collect.mutate()}>
            {collect.isPending ? "수집 중…" : "수집"}
          </button>
        </div>
        {collect.data && <div style={{ marginTop: 8 }}>✅ {collect.data.total_articles}건 수집</div>}
        {collect.error && (
          <div style={{ marginTop: 8, color: "var(--semantic-danger)" }}>{(collect.error as Error).message}</div>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        {[1, 7, 30].map((d) => (
          <button key={d} className={`btn${d === days ? " primary" : ""}`} style={{ marginRight: 6 }} onClick={() => setDays(d)}>
            {d === 1 ? "오늘" : `${d}일`}
          </button>
        ))}
      </div>

      {news.isLoading && <div className="muted">불러오는 중…</div>}
      {news.data?.length === 0 && <div className="muted">수집된 기사가 없습니다.</div>}
      {news.data?.map((a) => (
        <div className="card" key={a.link}>
          <div style={{ fontWeight: 600 }}>
            <a href={a.link} target="_blank" rel="noreferrer">{a.title}</a>
          </div>
          <div className="muted" style={{ fontSize: "var(--fs-caption)", margin: "4px 0" }}>
            {a.source} · {a.press} · {a.date}
          </div>
          {(a.summary_llm || a.summary) && <div>{a.summary_llm || a.summary}</div>}
          {a.keywords && (
            <div style={{ marginTop: 6 }}>
              {a.keywords.split(",").map((k) => (
                <span key={k} className="chip">{k.trim()}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
