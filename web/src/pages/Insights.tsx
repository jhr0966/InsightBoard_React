import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { KPIStatGrid, EmptyState, Badge, Tabs, LoadError, clickableProps } from "../components/ui";
import LineChart from "../components/charts/LineChart";
import BubbleMatrix from "../components/charts/BubbleMatrix";
import type { Bubble } from "../components/charts/BubbleMatrix";
import Heatmap from "../components/charts/Heatmap";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bd-sec">
      <div className="bd-sec-head">
        <span className="bd-sec-title">{title}</span>
      </div>
      {children}
    </section>
  );
}

function HeatmapDetail({ sel, days, onProposals }: { sel: string; days: number; onProposals: () => void }) {
  const [row, col] = sel.split("||");
  const cell = useQuery({ queryKey: ["insights", "heatmap-cell", row, col, days], queryFn: () => api.insights.heatmapCell(row, col, days) });
  const items = cell.data ?? [];
  return (
    <div className="ia-hm-detail">
      <div className="ia-hm-detail-head">
        <b>{row} × {col}</b>
        <span className="muted" style={{ fontSize: "var(--fs-caption)" }}>
          {cell.isLoading ? " · 불러오는 중…" : ` · 매칭 뉴스 ${items.length}건`}
        </span>
        <button className="btn" style={{ marginLeft: "auto" }} onClick={onProposals}>SOLA에서 더 보기 →</button>
      </div>
      {items.length > 0 ? (
        <div className="ia-hm-news">
          {items.slice(0, 3).map((a) => (
            <a key={a.link} className="ia-hm-news-item" href={a.link} target="_blank" rel="noreferrer noopener">
              <span className="ia-hm-news-title">{a.title}</span>
              <span className="muted" style={{ fontSize: "var(--fs-micro)" }}>{a.press || a.source || ""}</span>
            </a>
          ))}
        </div>
      ) : !cell.isLoading ? (
        <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>이 조합의 매칭 뉴스가 아직 없어요.</div>
      ) : null}
    </div>
  );
}

export default function Insights() {
  const nav = useNavigate();
  const [days, setDays] = useState(30);
  const [sel, setSel] = useState<string | null>(null);
  const [hmSel, setHmSel] = useState<string | null>(null);
  const [tkw, setTkw] = useState<string | null>(null);  // 선택한 트렌드 키워드(공정 매핑 필터)
  // Step 11: 분석 3종을 탭으로 — 한 번에 하나만(파고드는 층도 화면은 가볍게).
  const [tab, setTab] = useState<"trend" | "matrix" | "heatmap">("trend");

  const keywords = useQuery({ queryKey: ["trends", "keywords", days], queryFn: () => api.trends.keywords(days, 12) });
  const volume = useQuery({ queryKey: ["trends", "volume", days], queryFn: () => api.trends.volume(days) });
  const trend = useQuery({ queryKey: ["trends", "keyword-series"], queryFn: () => api.trends.keywordSeries() });
  const emergence = useQuery({ queryKey: ["trends", "emergence", days], queryFn: () => api.trends.emergence(days, 20) });
  const opps = useQuery({ queryKey: ["opportunities", days], queryFn: () => api.opportunities.list(days, 8) });
  const heatmap = useQuery({ queryKey: ["insights", "heatmap", days], queryFn: () => api.insights.heatmap(days) });

  // 활성 트렌드 키워드 — 선택값 우선, 없으면 상위 1위 키워드.
  const activeKw = tkw ?? keywords.data?.[0]?.keyword ?? "";
  const pmap = useQuery({
    queryKey: ["insights", "process-map", activeKw, days],
    queryFn: () => api.insights.processMap(activeKw, days, 3),
    enabled: !!activeKw,
  });

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
        <div className="ia-eyebrow">WORKFLOW / 분석실</div>
        <div className="ia-title">분석실</div>
        <div className="ia-desc">트렌드 · 공정 매칭 · PoC 후보를 한눈에.</div>
      </div>

      <KPIStatGrid items={[
        { label: `분석 뉴스 (${days}일)`, value: volume.data ? volume.data.reduce((s, v) => s + v.count, 0) : "…" },
        { label: "신규 트렌드", value: (emergence.data?.new ?? []).length, tone: "success" },
        { label: "매칭 공정", value: new Set((opps.data ?? []).map((c) => c.lv3)).size },
        { label: "PoC 후보", value: (opps.data ?? []).length, tone: "warning" },
      ]} />

      <div className="ia-filter" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Tabs items={[{ key: "trend", label: "📈 트렌드 → 공정" }, { key: "matrix", label: "🧭 기회 매트릭스" }, { key: "heatmap", label: "🔬 기술 히트맵" }]}
          value={tab} onChange={(t) => setTab(t as typeof tab)} />
        <span style={{ flex: 1 }} />
        {[7, 14, 30].map((d) => (
          <button key={d} className={`ia-filter-btn${d === days ? " on" : ""}`} onClick={() => setDays(d)}>{d}일</button>
        ))}
      </div>

      {/* 탭별 공용 오류 라인 — 조회 실패를 "데이터 부족"으로 오인하지 않게. */}
      {((tab === "trend" && (keywords.isError || volume.isError || trend.isError || emergence.isError))
        || (tab === "matrix" && opps.isError)
        || (tab === "heatmap" && heatmap.isError)) && (
        <div style={{ margin: "8px 0" }}>
          <LoadError compact message="이 탭의 분석 데이터를 불러오지 못했어요" onRetry={() => {
            if (tab === "trend") { keywords.refetch(); volume.refetch(); trend.refetch(); emergence.refetch(); }
            else if (tab === "matrix") opps.refetch();
            else heatmap.refetch();
          }} />
        </div>
      )}

      {/* A. 트렌드 → 공정 매핑 */}
      {tab === "trend" && <Section title="트렌드 → 공정 연결">
        <div className="chart-row">
          <div className="card" style={{ margin: 0 }}>
            <div className="card-title">키워드 트렌드 <span className="muted" style={{ fontWeight: 400 }}>· {trend.data?.mode === "daily" ? "최근 14일(일별)" : "최근 8주(주별)"}</span></div>
            {trend.data && trend.data.series.length > 0 ? (
              <>
                <LineChart labels={trend.data.labels}
                  series={trend.data.series.slice(0, 4).map((s) => ({ name: s.keyword, values: s.counts }))}
                  width={520} height={150} highlightTop={3} />
                {trend.data.anno && (
                  <div className="ia-trend-anno"><b>{trend.data.anno.name} {trend.data.anno.arrow}</b>
                    <span className="muted"> · {trend.data.anno.sub}</span></div>
                )}
              </>
            ) : <EmptyState icon="📈" title="트렌드 데이터 부족" hint="30일 이상 수집 후 키워드 추이가 표시됩니다." />}
          </div>
          <div className="card" style={{ margin: 0 }}>
            <div className="card-title">트렌드 키워드 <span className="muted" style={{ fontWeight: 400 }}>· 상승순</span></div>
            <div className="muted" style={{ fontSize: "var(--fs-micro)", marginBottom: 4 }}>키워드를 누르면 연결 공정이 바뀝니다</div>
            {(keywords.data ?? []).map((k, i) => (
              <div className={`ia-kw${k.keyword === activeKw ? " on" : ""}`} key={k.keyword}
                style={{ cursor: "pointer" }}
                {...clickableProps(() => setTkw(k.keyword === activeKw ? null : k.keyword), `${k.keyword} 트렌드 선택`)}>
                <span className="ia-kw-rank">{String(i + 1).padStart(2, "0")}</span>
                <span className="ia-kw-name">{k.keyword} {newSet.has(k.keyword) && <Badge tone="success">NEW</Badge>}</span>
                <span className="ia-kw-bar" style={{ width: `${(k.count / kwMax) * 90}px` }} />
                <span className="muted" style={{ fontSize: "var(--fs-micro)", width: 28, textAlign: "right" }}>{k.count}</span>
              </div>
            ))}
            {keywords.data?.length === 0 && <span className="muted">데이터 없음</span>}
          </div>
        </div>

        {/* 트렌드 키워드 → 연결 공정 카드 */}
        {activeKw && (
          <div className="card" style={{ marginTop: 12 }}>
            <div className="card-title">🔗 ‘{activeKw}’ 연결 공정 <span className="muted" style={{ fontWeight: 400 }}>· 적합도순 상위 3</span></div>
            {pmap.isLoading ? <span className="muted">분석 중…</span>
              : (pmap.data?.length ?? 0) === 0
                ? <span className="muted">이 키워드에 매칭되는 공정이 없어요.</span>
                : <div className="ia-pmap">
                  {pmap.data!.map((p) => (
                    <div className="ia-pmap-card" key={`${p.dept}||${p.lv3}`}
                      {...clickableProps(() => setSel(`${p.dept}||${p.lv3}`), `${p.dept} ${p.lv3} 선택`)} style={{ cursor: "pointer" }}>
                      <div className="ia-pmap-head">
                        <span className="ia-pmap-proc">{p.dept} · {p.lv3}</span>
                        <Badge tone={p.tag === "PoC 후보" ? "warning" : "default"}>{p.tag}</Badge>
                      </div>
                      <div className="ia-pmap-fit">
                        <span className="ia-pmap-bar" style={{ width: `${Math.round(p.fit * 100)}%` }} />
                        <span className="muted" style={{ fontSize: "var(--fs-micro)" }}>적합도 {Math.round(p.fit * 100)}% · 근거 {p.matched_news}건</span>
                      </div>
                      {p.objective && <div className="ia-pmap-obj">{p.objective}</div>}
                      {p.signal && <div className="muted ia-pmap-sig">📰 {p.signal}</div>}
                    </div>
                  ))}
                </div>}
          </div>
        )}
      </Section>}

      {/* B. 매트릭스 + PoC 랭킹 */}
      {tab === "matrix" && <Section title="자동화 기회 매트릭스">
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
      </Section>}

      {/* C. 히트맵 */}
      {tab === "heatmap" && <Section title="공정 × 자동화 기술 히트맵">
        {(heatmap.data?.rows.length ?? 0) === 0
          ? <EmptyState icon="🔬" title="공정 × 기술 매칭이 아직 없어요" hint="작업정의 업로드 + 뉴스 수집 후 표시됩니다." />
          : <div className="card" style={{ margin: 0 }}>
            <Heatmap rows={heatmap.data!.rows} cols={heatmap.data!.cols} data={heatmap.data!.data}
              selected={hmSel} onSelect={setHmSel} />
            {hmSel && <HeatmapDetail sel={hmSel} days={days}
              onProposals={() => nav(`/proposals?from=insights&lv3=${encodeURIComponent(hmSel.split("||")[0])}`)} />}
          </div>}
      </Section>}
    </div>
  );
}
