import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

// 오늘의 보드 — 다이제스트(최근 뉴스 수 + 상위 키워드).
export default function Board() {
  const news = useQuery({ queryKey: ["news", 1], queryFn: () => api.news.today() });
  const kw = useQuery({ queryKey: ["trends", "keywords", 7], queryFn: () => api.trends.keywords(7, 8) });
  const brief = useQuery({ queryKey: ["board", "brief"], queryFn: () => api.board.brief(1) });

  return (
    <div>
      <h1 className="page-title">📊 오늘의 보드</h1>
      <div className="card">
        <strong>요약</strong>
        {brief.isLoading && <div className="muted">생성 중…</div>}
        {brief.data && (
          <>
            {brief.data.persona_label && brief.data.persona_label !== "(미설정)" && (
              <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>{brief.data.persona_label}</div>
            )}
            <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{brief.data.brief}</div>
          </>
        )}
      </div>
      <div className="card">
        <strong>오늘 수집</strong>{" "}
        <span className="muted">{news.isLoading ? "…" : `${news.data?.length ?? 0}건`}</span>
      </div>
      <div className="card">
        <strong>최근 7일 상위 키워드</strong>
        <div style={{ marginTop: 10 }}>
          {kw.isLoading && <span className="muted">불러오는 중…</span>}
          {kw.data?.map((k) => (
            <span key={k.keyword} className="chip">
              {k.keyword} · {k.count}
            </span>
          ))}
          {kw.data?.length === 0 && <span className="muted">데이터 없음</span>}
        </div>
      </div>
    </div>
  );
}
