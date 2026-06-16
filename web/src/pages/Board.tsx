import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, Chip, EmptyState, KPIStatGrid } from "../components/ui";

// 오늘의 보드 — KPI + SOLA 브리핑 + 상위 키워드 (P2 에서 탑스토리·매트릭스·트렌드 확장).
export default function Board() {
  const news = useQuery({ queryKey: ["news", 1], queryFn: () => api.news.today() });
  const kw = useQuery({ queryKey: ["trends", "keywords", 7], queryFn: () => api.trends.keywords(7, 8) });
  const brief = useQuery({ queryKey: ["board", "brief"], queryFn: () => api.board.brief(1) });
  const summary = useQuery({ queryKey: ["bookmarks", "summary"], queryFn: () => api.bookmarks.summary() });

  const status = (summary.data?.proposal_status as Record<string, number> | undefined) ?? {};
  const proposals = (summary.data?.by_type as Record<string, number> | undefined)?.proposal ?? 0;

  return (
    <div>
      <KPIStatGrid
        items={[
          { label: "오늘 수집", value: news.isLoading ? "…" : (news.data?.length ?? 0) },
          { label: "자동화 제안", value: proposals },
          { label: "채택", value: status.adopted ?? 0, tone: "success" },
          { label: "채택 대기", value: status.pending ?? 0, tone: "warning" },
        ]}
      />

      <Card title="SOLA 오늘의 브리핑">
        {brief.isLoading && <div className="muted">생성 중…</div>}
        {brief.data && (
          <>
            {brief.data.persona_label && brief.data.persona_label !== "(미설정)" && (
              <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>{brief.data.persona_label}</div>
            )}
            <div style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>{brief.data.brief}</div>
          </>
        )}
      </Card>

      <Card title="최근 7일 상위 키워드">
        {kw.isLoading && <span className="muted">불러오는 중…</span>}
        {kw.data?.map((k) => <Chip key={k.keyword}>{k.keyword} · {k.count}</Chip>)}
        {kw.data?.length === 0 && (
          <EmptyState icon="🗞" title="아직 수집된 뉴스가 없어요" hint="뉴스 수집에서 수집을 시작하세요." />
        )}
      </Card>
    </div>
  );
}
