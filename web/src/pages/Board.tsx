import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { KPIStatGrid, EmptyState } from "../components/ui";
import { useToast } from "../components/ui/toast";
import NewsCard from "../components/NewsCard";
import BubbleMatrix from "../components/charts/BubbleMatrix";
import type { Bubble } from "../components/charts/BubbleMatrix";
import BarChart from "../components/charts/BarChart";
import Sparkline from "../components/charts/Sparkline";

function Section({ title, note, cta, children }: {
  title: string; note?: string; cta?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="bd-sec">
      <div className="bd-sec-head">
        <span className="bd-sec-title">{title}</span>
        {note && <span className="bd-sec-note">{note}</span>}
        {cta && <span className="bd-sec-cta">{cta}</span>}
      </div>
      {children}
    </section>
  );
}

export default function Board() {
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [sel, setSel] = useState<string | null>(null);

  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const summary = useQuery({ queryKey: ["bookmarks", "summary"], queryFn: () => api.bookmarks.summary() });
  const today = useQuery({ queryKey: ["news", "today"], queryFn: () => api.news.today() });
  const brief = useQuery({ queryKey: ["board", "brief"], queryFn: () => api.board.brief(1) });
  const opps = useQuery({ queryKey: ["opportunities", 30], queryFn: () => api.opportunities.list(30, 6) });
  const volume = useQuery({ queryKey: ["trends", "volume", 14], queryFn: () => api.trends.volume(14) });
  const keywords = useQuery({ queryKey: ["trends", "keywords", 30], queryFn: () => api.trends.keywords(30, 8) });

  const status = (summary.data?.proposal_status as Record<string, number> | undefined) ?? {};
  const proposals = (summary.data?.by_type as Record<string, number> | undefined)?.proposal ?? 0;
  const news = today.data ?? [];

  const bubbles: Bubble[] = useMemo(() => {
    const cells = opps.data ?? [];
    const maxScore = Math.max(1, ...cells.map((c) => c.cell_score));
    const maxAvg = Math.max(0.01, ...cells.map((c) => c.avg_score));
    return cells.map((c) => ({
      key: `${c.dept}||${c.lv3}`, label: c.lv3, dept: c.dept,
      ease: Math.min(1, c.avg_score / maxAvg), impact: Math.min(1, c.cell_score / maxScore), score: c.cell_score,
    }));
  }, [opps.data]);
  const selCell = (opps.data ?? []).find((c) => `${c.dept}||${c.lv3}` === sel);

  const collect = useMutation({
    mutationFn: () => api.collect.run(persona.data?.interest_keywords ?? [], { do_enrich: false }),
    onSuccess: (r) => { toast.push(`✅ ${r.total_articles}건 수집했어요`, "success"); qc.invalidateQueries({ queryKey: ["news"] }); },
    onError: (e) => toast.push(`⚠️ 수집 실패: ${(e as Error).message}`, "danger"),
  });

  const name = persona.data?.name || persona.data?.dept || "";
  const now = new Date();

  return (
    <div>
      {/* ① 인사말 + KPI */}
      <div className="bd-greet">
        <div className="bd-greet-hi">안녕하세요{name ? `, ${name}님` : ""} 👋</div>
        <div className="bd-greet-sub">
          {persona.data?.is_set ? persona.data.label : "페르소나를 설정하면 더 맞춤화됩니다"}
          {" · "}{now.getMonth() + 1}월 {now.getDate()}일 {String(now.getHours()).padStart(2, "0")}:{String(now.getMinutes()).padStart(2, "0")} 기준
        </div>
      </div>
      <KPIStatGrid items={[
        { label: "오늘 수집", value: today.isLoading ? "…" : news.length },
        { label: "자동화 제안", value: proposals },
        { label: "채택", value: status.adopted ?? 0, tone: "success" },
        { label: "채택 대기", value: status.pending ?? 0, tone: "warning" },
      ]} />

      {/* ② SOLA 브리핑 + 캐러셀 */}
      <Section title="SOLA 오늘의 브리핑" note="아침 7분"
        cta={news.length > 0 && <button className="btn primary" onClick={() => nav("/proposals?from=brief")}>이 뉴스로 제안서 →</button>}>
        <div className="bd-brief">
          <span className="bd-brief-tag">요약</span>
          {brief.isLoading ? <div className="skel" style={{ height: 40, marginTop: 12 }} />
            : <div className="bd-brief-text">{brief.data?.brief}</div>}
          {news.length > 0 && (
            <div className="bd-carousel" style={{ marginTop: "var(--space-4)" }}>
              {news.slice(0, 6).map((a) => <NewsCard key={a.link} article={a} compact />)}
            </div>
          )}
        </div>
      </Section>

      {/* ③ 탑 스토리 */}
      <Section title="탑 스토리" note="최근 수집 주요 기사">
        {today.isLoading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
          : news.length === 0 ? <EmptyState icon="🗞" title="아직 수집된 뉴스가 없어요" hint="아래 키워드 관리에서 수집을 시작하세요." />
          : <div className="bd-grid">{news.slice(0, 6).map((a) => <NewsCard key={a.link} article={a} />)}</div>}
      </Section>

      {/* ④ 자동화 제안 카드 */}
      <Section title="자동화 제안" note="부서 × 공정 기회 상위">
        {opps.data?.length === 0 ? <EmptyState icon="🤖" title="아직 매칭된 자동화 제안이 없어요" hint="뉴스·작업정의가 쌓이면 표시됩니다." />
          : <div className="bd-opps">
            {(opps.data ?? []).slice(0, 3).map((c) => (
              <div className="bd-opp" key={`${c.dept}-${c.lv3}`}>
                <div className="bd-opp-top">
                  <span className="bd-opp-dept">{c.dept} · {c.lv3}</span>
                  <span className="badge badge-accent">{c.cell_score.toFixed(0)}</span>
                </div>
                <div className="bd-opp-metrics">
                  <span><b>{c.matched_news}</b> 뉴스</span>
                  <span><b>{c.matched_tasks}</b> 작업</span>
                </div>
                {c.sample_tasks && <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>{c.sample_tasks}</div>}
                <button className="btn" style={{ marginTop: "auto" }} onClick={() => nav(`/proposals?from=board&dept=${encodeURIComponent(c.dept)}&lv3=${encodeURIComponent(c.lv3)}`)}>SOLA 검토 →</button>
              </div>
            ))}
          </div>}
      </Section>

      {/* ⑤ 기회 매트릭스 */}
      <Section title="기회 매트릭스" note="난이도 × 효과">
        {bubbles.length === 0 ? <EmptyState icon="🧭" title="매트릭스를 그릴 데이터가 부족해요" />
          : <div className="chart-row">
            <BubbleMatrix cells={bubbles} selectedKey={sel} onSelect={setSel} height={360} />
            <div>
              {selCell ? <>
                <div style={{ fontWeight: 600 }}>{selCell.dept} · {selCell.lv3}</div>
                <div style={{ display: "flex", gap: 12, margin: "8px 0" }}>
                  <span><b>{selCell.cell_score.toFixed(1)}</b> <span className="muted">점수</span></span>
                  <span><b>{selCell.matched_news}</b> <span className="muted">뉴스</span></span>
                </div>
                <button className="btn primary" onClick={() => nav(`/proposals?from=matrix&dept=${encodeURIComponent(selCell.dept)}&lv3=${encodeURIComponent(selCell.lv3)}`)}>제안서 작업장 →</button>
              </> : <div className="muted">버블을 클릭하면 상세가 표시됩니다.</div>}
            </div>
          </div>}
      </Section>

      {/* ⑥ 트렌드 */}
      <Section title="수집 트렌드" note="최근 14일">
        <div className="chart-row">
          <div className="card" style={{ margin: 0 }}>
            {volume.data && volume.data.length > 0
              ? <BarChart bars={volume.data.map((v, i, arr) => ({ label: v.date, value: v.count, title: `${v.date}: ${v.count}건`, highlight: i === arr.length - 1 }))} width={560} height={100} />
              : <div className="muted">데이터 부족</div>}
          </div>
          <div className="card" style={{ margin: 0 }}>
            {(keywords.data ?? []).slice(0, 6).map((k) => (
              <div className="bd-trend-kw" key={k.keyword}>
                <span className="bd-trend-kw-name">{k.keyword}</span>
                <Sparkline values={[Math.max(0, k.count - 2), k.count - 1, k.count]} />
                <span className="badge badge-default">{k.count}</span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ⑦ 키워드 관리 */}
      <Section title="내 키워드" note="관심사 + 자동 추출"
        cta={<button className="btn primary" disabled={collect.isPending} onClick={() => collect.mutate()}>
          {collect.isPending ? "수집 중…" : "지금 수집 →"}</button>}>
        <div className="card" style={{ margin: 0 }}>
          <div className="bd-kw-line">
            {(persona.data?.interest_keywords ?? []).map((k) => <span key={k} className="bd-kw bd-kw-strong">{k}</span>)}
            {(keywords.data ?? []).slice(0, 8).map((k) => (
              <span key={k.keyword} className="bd-kw">{k.keyword}<span className="bd-kw-n">{k.count}</span></span>
            ))}
            {(persona.data?.interest_keywords ?? []).length === 0 && (keywords.data ?? []).length === 0 &&
              <span className="muted">키워드가 없어요. 페르소나에서 관심 키워드를 추가하세요.</span>}
          </div>
        </div>
      </Section>
    </div>
  );
}
