import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { KPIStatGrid, EmptyState, Badge } from "../components/ui";
import BarChart from "../components/charts/BarChart";
import BubbleMatrix from "../components/charts/BubbleMatrix";
import type { Bubble } from "../components/charts/BubbleMatrix";
import Heatmap from "../components/charts/Heatmap";

function Section({ title, step, children }: { title: string; step?: string; children: React.ReactNode }) {
  return (
    <section className="bd-sec">
      <div className="bd-sec-head">
        {step && <Badge tone="accent">{step}</Badge>}
        <span className="bd-sec-title">{title}</span>
      </div>
      {children}
    </section>
  );
}

export default function Insights() {
  const nav = useNavigate();
  const [days, setDays] = useState(30);
  const [sel, setSel] = useState<string | null>(null);
  const [hmSel, setHmSel] = useState<string | null>(null);

  const keywords = useQuery({ queryKey: ["trends", "keywords", days], queryFn: () => api.trends.keywords(days, 12) });
  const volume = useQuery({ queryKey: ["trends", "volume", days], queryFn: () => api.trends.volume(days) });
  const emergence = useQuery({ queryKey: ["trends", "emergence", days], queryFn: () => api.trends.emergence(days, 20) });
  const opps = useQuery({ queryKey: ["opportunities", days], queryFn: () => api.opportunities.list(days, 8) });
  const heatmap = useQuery({ queryKey: ["insights", "heatmap", days], queryFn: () => api.insights.heatmap(days) });

  const newSet = new Set((emergence.data?.new ?? []).map((k) => k.keyword));
  const kwMax = Math.max(1, ...(keywords.data ?? []).map((k) => k.count));

  const bubbles: Bubble[] = useMemo(() => {
    const cells = opps.data ?? [];
    const maxScore = Math.max(1, ...cells.map((c) => c.cell_score));
    const maxAvg = Math.max(0.01, ...cells.map((c) => c.avg_score));
    return cells.map((c) => ({
      key: `${c.dept}||${c.lv3}`, label: c.lv3, dept: c.dept,
      ease: Math.min(1, c.avg_score / maxAvg), impact: Math.min(1, c.cell_score / maxScore), score: c.cell_score,
    }));
  }, [opps.data]);

  return (
    <div>
      <div className="ia-head">
        <div className="ia-eyebrow">WORKFLOW / 인사이트 분석</div>
        <div className="ia-title">자동화 제안 분석실</div>
        <div className="ia-desc">트렌드 · 공정 매칭 · PoC 후보를 한눈에.</div>
      </div>

      <KPIStatGrid items={[
        { label: `분석 뉴스 (${days}일)`, value: volume.data ? volume.data.reduce((s, v) => s + v.count, 0) : "…" },
        { label: "신규 트렌드", value: (emergence.data?.new ?? []).length, tone: "success" },
        { label: "매칭 공정", value: new Set((opps.data ?? []).map((c) => c.lv3)).size },
        { label: "PoC 후보", value: (opps.data ?? []).length, tone: "warning" },
      ]} />

      <div className="ia-filter">
        {[7, 14, 30].map((d) => (
          <button key={d} className={`ia-filter-btn${d === days ? " on" : ""}`} onClick={() => setDays(d)}>{d}일</button>
        ))}
      </div>

      {/* A. 트렌드 → 공정 매핑 */}
      <Section title="트렌드 → 공정 연결" step="STEP 1">
        <div className="chart-row">
          <div className="card" style={{ margin: 0 }}>
            <div className="card-title">일자별 수집량</div>
            {volume.data && volume.data.length > 0
              ? <BarChart bars={volume.data.map((v, i, a) => ({ label: v.date, value: v.count, title: `${v.date}: ${v.count}건`, highlight: i === a.length - 1 }))} width={520} height={120} />
              : <EmptyState icon="📈" title="트렌드 데이터 부족" hint="30일 이상 수집 후 표시됩니다." />}
          </div>
          <div className="card" style={{ margin: 0 }}>
            <div className="card-title">트렌드 키워드 <span className="muted" style={{ fontWeight: 400 }}>· 상승순</span></div>
            {(keywords.data ?? []).map((k, i) => (
              <div className="ia-kw" key={k.keyword}>
                <span className="ia-kw-rank">{String(i + 1).padStart(2, "0")}</span>
                <span className="ia-kw-name">{k.keyword} {newSet.has(k.keyword) && <Badge tone="success">NEW</Badge>}</span>
                <span className="ia-kw-bar" style={{ width: `${(k.count / kwMax) * 90}px` }} />
                <span className="muted" style={{ fontSize: "var(--fs-micro)", width: 28, textAlign: "right" }}>{k.count}</span>
              </div>
            ))}
            {keywords.data?.length === 0 && <span className="muted">데이터 없음</span>}
          </div>
        </div>
      </Section>

      {/* B. 매트릭스 + PoC 랭킹 */}
      <Section title="자동화 제안 매트릭스" step="STEP 2">
        {bubbles.length === 0 ? <EmptyState icon="🧭" title="아직 매칭된 자동화 제안이 없어요" hint="뉴스·작업정의(로드맵)가 필요합니다." />
          : <div className="chart-row">
            <BubbleMatrix cells={bubbles} selectedKey={sel} onSelect={setSel} />
            <div className="card" style={{ margin: 0 }}>
              <div className="card-title">★ PoC 후보 <span className="muted" style={{ fontWeight: 400 }}>({bubbles.length})</span></div>
              {(opps.data ?? []).map((c, i) => {
                const key = `${c.dept}||${c.lv3}`;
                return (
                  <div key={key} className={`ia-poc${key === sel ? " on" : ""}`} onClick={() => setSel(key)}>
                    <span className="ia-poc-rank">{String(i + 1).padStart(2, "0")}</span>
                    <span className="ia-poc-name">{c.dept} · {c.lv3}</span>
                    <span className="ia-poc-score">{c.cell_score.toFixed(0)}</span>
                  </div>
                );
              })}
            </div>
          </div>}
      </Section>

      {/* C. 히트맵 */}
      <Section title="공정 × 자동화 기술 히트맵" step="STEP 3">
        {(heatmap.data?.rows.length ?? 0) === 0
          ? <EmptyState icon="🔬" title="공정 × 기술 매칭이 아직 없어요" hint="작업정의 업로드 + 뉴스 수집 후 표시됩니다." />
          : <div className="card" style={{ margin: 0 }}>
            <Heatmap rows={heatmap.data!.rows} cols={heatmap.data!.cols} data={heatmap.data!.data}
              selected={hmSel} onSelect={setHmSel} />
            {hmSel && <div className="ia-hm-detail">
              <b>{hmSel.replace("||", " × ")}</b> — 관련 뉴스 매칭{" "}
              <button className="btn" style={{ marginLeft: 8 }} onClick={() => nav("/proposals")}>SOLA에서 더 보기 →</button>
            </div>}
          </div>}
      </Section>
    </div>
  );
}
