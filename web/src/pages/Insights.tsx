import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// 인사이트 분석 — 트렌드(키워드/볼륨/출처).
export default function Insights() {
  const [days, setDays] = useState(7);
  const keywords = useQuery({ queryKey: ["trends", "keywords", days], queryFn: () => api.trends.keywords(days, 20) });
  const volume = useQuery({ queryKey: ["trends", "volume", days], queryFn: () => api.trends.volume(days) });
  const sources = useQuery({ queryKey: ["trends", "sources", days], queryFn: () => api.trends.sources(days) });

  return (
    <div>
      <h1 className="page-title">🔎 인사이트 분석</h1>
      <div style={{ marginBottom: 16 }}>
        기간:{" "}
        {[7, 14, 30].map((d) => (
          <button key={d} className={`btn${d === days ? " primary" : ""}`} style={{ marginRight: 6 }} onClick={() => setDays(d)}>
            {d}일
          </button>
        ))}
      </div>

      <div className="card">
        <strong>상위 키워드</strong>
        <div style={{ marginTop: 10 }}>
          {keywords.data?.map((k) => (
            <span key={k.keyword} className="chip">{k.keyword} · {k.count}</span>
          ))}
          {keywords.data?.length === 0 && <span className="muted">데이터 없음</span>}
        </div>
      </div>

      <div className="card">
        <strong>일자별 볼륨</strong>
        <ul>
          {volume.data?.map((v) => (
            <li key={v.date}>{v.date} — {v.count}건</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <strong>출처별 분포</strong>
        <div style={{ marginTop: 10 }}>
          {sources.data?.map((s) => (
            <span key={s.source} className="chip">{s.source} · {s.count}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
