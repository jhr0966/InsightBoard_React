import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, Chip, EmptyState } from "../components/ui";
import BarChart from "../components/charts/BarChart";
import Sparkline from "../components/charts/Sparkline";
import BubbleMatrix from "../components/charts/BubbleMatrix";
import type { Bubble } from "../components/charts/BubbleMatrix";

// 인사이트 분석 — 트렌드 차트(볼륨·키워드 스파크라인) + 자동화 기회 버블 매트릭스.
export default function Insights() {
  const [days, setDays] = useState(30);
  const [sel, setSel] = useState<string | null>(null);
  const keywords = useQuery({ queryKey: ["trends", "keywords", days], queryFn: () => api.trends.keywords(days, 12) });
  const volume = useQuery({ queryKey: ["trends", "volume", days], queryFn: () => api.trends.volume(days) });
  const opps = useQuery({ queryKey: ["opportunities", days], queryFn: () => api.opportunities.list(days, 8) });

  const bars = (volume.data ?? []).map((v, i, arr) => ({
    label: v.date, value: v.count, title: `${v.date}: ${v.count}건`, highlight: i === arr.length - 1,
  }));

  // 기회 셀 → 버블 정규화
  const bubbles: Bubble[] = useMemo(() => {
    const cells = opps.data ?? [];
    const maxScore = Math.max(1, ...cells.map((c) => c.cell_score));
    const maxAvg = Math.max(0.01, ...cells.map((c) => c.avg_score));
    return cells.map((c) => ({
      key: `${c.dept}||${c.lv3}`,
      label: c.lv3,
      dept: c.dept,
      ease: Math.min(1, c.avg_score / maxAvg),
      impact: Math.min(1, c.cell_score / maxScore),
      score: c.cell_score,
    }));
  }, [opps.data]);

  const selCell = (opps.data ?? []).find((c) => `${c.dept}||${c.lv3}` === sel);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        기간:{" "}
        {[7, 14, 30].map((d) => (
          <button key={d} className={`btn${d === days ? " primary" : ""}`} style={{ marginRight: 6 }} onClick={() => setDays(d)}>
            {d}일
          </button>
        ))}
      </div>

      <Card title="일자별 수집량">
        {bars.length === 0 ? <EmptyState icon="📈" title="트렌드 데이터 부족" hint="수집 후 표시됩니다." />
          : <BarChart bars={bars} width={560} height={90} />}
      </Card>

      <Card title="상위 키워드">
        {keywords.data?.map((k) => (
          <div key={k.keyword} style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
            <span style={{ flex: 1 }}>{k.keyword}</span>
            <Sparkline values={[Math.max(0, k.count - 2), k.count - 1, k.count]} />
            <Chip>{k.count}</Chip>
          </div>
        ))}
        {keywords.data?.length === 0 && <span className="muted">데이터 없음</span>}
      </Card>

      <Card title="🤖 자동화 기회 매트릭스 (부서 × 공정)">
        {opps.isLoading && <div className="muted">계산 중…</div>}
        {opps.data?.length === 0 && (
          <EmptyState icon="🧭" title="아직 매칭된 자동화 제안이 없어요" hint="뉴스·작업정의(로드맵) 데이터가 필요합니다." />
        )}
        {bubbles.length > 0 && (
          <div className="chart-row">
            <BubbleMatrix cells={bubbles} selectedKey={sel} onSelect={setSel} />
            <div>
              {selCell ? (
                <>
                  <div style={{ fontWeight: 600 }}>{selCell.dept} · {selCell.lv3}</div>
                  <div style={{ display: "flex", gap: 12, margin: "8px 0" }}>
                    <span><b>{selCell.cell_score.toFixed(1)}</b> <span className="muted">점수</span></span>
                    <span><b>{selCell.matched_news}</b> <span className="muted">뉴스</span></span>
                    <span><b>{selCell.matched_tasks}</b> <span className="muted">작업</span></span>
                  </div>
                  {selCell.sample_tasks && <div className="muted">{selCell.sample_tasks}</div>}
                </>
              ) : (
                <div className="muted">버블을 클릭하면 상세가 표시됩니다.</div>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
