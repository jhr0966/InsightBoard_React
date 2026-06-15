import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// 뉴스 수집 — 최근 기사 카드 목록.
export default function Collect() {
  const [days, setDays] = useState(7);
  const news = useQuery({ queryKey: ["news", days], queryFn: () => api.news.list({ days, limit: 60 }) });

  return (
    <div>
      <h1 className="page-title">🗞 뉴스 수집</h1>
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
