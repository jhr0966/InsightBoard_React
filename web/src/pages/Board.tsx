import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { DigestItem } from "../api/types";
import { EmptyState } from "../components/ui";
import { useToast } from "../components/ui/toast";

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

// 오늘의 다이제스트 — 개인화 기사 3~5건 + 왜 관련 + 저장/관련없음 (Step 9).
// 노출(impression)·저장(save)·관련없음(dismiss) 이벤트를 기록해 랭킹 개선의
// 원자료로 쓴다 — '관련 없음'은 숨김이 아니라 저장되는 신호(계획 §12).
function DigestSection() {
  const qc = useQueryClient();
  const toast = useToast();
  const digest = useQuery({ queryKey: ["board", "digest"], queryFn: () => api.board.digest(5, 3) });
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const impressedRef = useRef(false);

  useEffect(() => {
    // 노출 이벤트 — 1회만(재렌더 중복 방지). 실패는 무시(랭킹 평가용 로그).
    const items = digest.data?.items ?? [];
    if (!items.length || impressedRef.current) return;
    impressedRef.current = true;
    void api.feedback.send(items.map((it) => ({
      action_type: "impression", article_id: it.article_id,
      context: "board_digest", ranking_version: it.ranking_version,
    }))).catch(() => undefined);
  }, [digest.data]);

  const dismiss = useMutation({
    mutationFn: (it: DigestItem) => api.feedback.send([{
      action_type: "dismiss", article_id: it.article_id,
      context: "board_digest", ranking_version: it.ranking_version,
    }]),
    onSuccess: (_d, it) => {
      setHidden((h) => new Set(h).add(it.article_id));
      toast.push("이 기사와 비슷한 항목의 우선순위를 낮출게요", "default");
      qc.invalidateQueries({ queryKey: ["board", "digest"] });
    },
  });
  const saveArticle = useMutation({
    mutationFn: async (it: DigestItem) => {
      await api.bookmarks.create({ type: "news", title: it.title, link: it.link,
        content: it.excerpt ?? "" });
      await api.feedback.send([{ action_type: "save", article_id: it.article_id,
        context: "board_digest", ranking_version: it.ranking_version }]);
    },
    onSuccess: () => toast.push("💾 저장했어요", "success"),
  });

  const items = (digest.data?.items ?? []).filter((it) => !hidden.has(it.article_id));
  return (
    <Section title="오늘의 다이제스트" note="내 업무 기준 상위 기사">
      {digest.isLoading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
        : items.length === 0 ? <EmptyState icon="🗞" title="다이제스트가 비어 있어요"
            hint={digest.data?.persona_set ? "수집이 쌓이면 내 업무 관련 기사가 골라집니다." : "페르소나를 설정하면 내 업무 기준으로 골라드려요."} />
        : <div style={{ display: "grid", gap: 10 }}>
          {items.map((it) => (
            <div className="card" key={it.article_id} style={{ margin: 0, display: "grid", gap: 6 }}>
              <a href={it.link} target="_blank" rel="noreferrer noopener"
                style={{ fontWeight: 600, lineHeight: 1.4 }}
                onClick={() => void api.feedback.send([{ action_type: "open",
                  article_id: it.article_id, context: "board_digest",
                  ranking_version: it.ranking_version }]).catch(() => undefined)}>
                {it.title}
              </a>
              {it.excerpt && <div className="muted" style={{ fontSize: "var(--fs-caption)", lineHeight: 1.6 }}>{it.excerpt}</div>}
              {it.why && <div style={{ fontSize: "var(--fs-caption)" }}>💡 {it.why}</div>}
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span className="muted" style={{ fontSize: "var(--fs-micro)", marginRight: "auto" }}>
                  {it.press || it.source}{it.linked_task ? ` · ${it.linked_task}` : ""}
                </span>
                <button className="oa-mini" disabled={saveArticle.isPending}
                  onClick={() => saveArticle.mutate(it)}>💾 저장</button>
                <button className="oa-mini" disabled={dismiss.isPending}
                  onClick={() => dismiss.mutate(it)}>관련 없음</button>
              </div>
            </div>
          ))}
        </div>}
    </Section>
  );
}


export default function Board() {
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();

  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const brief = useQuery({ queryKey: ["board", "brief"], queryFn: () => api.board.brief(1) });
  const opps = useQuery({ queryKey: ["opportunities", 30], queryFn: () => api.opportunities.list(30, 3) });
  const keywords = useQuery({ queryKey: ["trends", "keywords", 30], queryFn: () => api.trends.keywords(30, 8) });

  const collect = useMutation({
    mutationFn: () => api.collect.run(persona.data?.interest_keywords ?? [], { do_enrich: false }),
    onSuccess: (r) => { toast.push(`✅ ${r.total_articles}건 수집했어요`, "success"); qc.invalidateQueries({ queryKey: ["news"] }); },
    onError: (e) => toast.push(`⚠️ 수집 실패: ${(e as Error).message}`, "danger"),
  });

  const name = persona.data?.name || persona.data?.dept || "";
  const now = new Date();

  // Step 11 홈 다이어트 — "부담 없이 읽는" 3분 화면: 인사말 → 한 줄 브리핑 →
  // 개인화 다이제스트 → 자동화 제안 3장 → 내 키워드. KPI·매트릭스·트렌드 차트는
  // 분석실(/insights)로 이관(중복 제거).
  return (
    <div>
      {/* ① 인사말 */}
      <div className="bd-greet">
        <div className="bd-greet-hi">안녕하세요{name ? `, ${name}님` : ""} 👋</div>
        <div className="bd-greet-sub">
          {persona.data?.is_set ? persona.data.label : "페르소나를 설정하면 더 맞춤화됩니다"}
          {" · "}{now.getMonth() + 1}월 {now.getDate()}일 {String(now.getHours()).padStart(2, "0")}:{String(now.getMinutes()).padStart(2, "0")} 기준
        </div>
      </div>

      {/* ② SOLA 한 줄 브리핑 */}
      <Section title="SOLA 오늘의 브리핑" note="오늘 내 업무 기준 요약"
        cta={<button className="btn primary" onClick={() => nav("/proposals?from=brief")}>이 뉴스로 제안서 →</button>}>
        <div className="bd-brief">
          <span className="bd-brief-tag">요약</span>
          {brief.isLoading ? <div className="skel" style={{ height: 40, marginTop: 12 }} />
            : brief.isError ? <div className="bd-brief-text muted">브리핑을 불러오지 못했어요 — {(brief.error as Error).message}</div>
            : <div className="bd-brief-text">{brief.data?.brief}</div>}
        </div>
      </Section>

      {/* ③ 오늘의 다이제스트 — 개인화 랭킹 + "왜 내 업무 관련" */}
      <DigestSection />

      {/* ④ 자동화 제안 상위 3 — 행동 유도 카드(상세 분석은 분석실) */}
      <Section title="자동화 제안" note="부서 × 공정 기회 상위"
        cta={<button className="btn" onClick={() => nav("/insights")}>분석실에서 더 보기 →</button>}>
        {(opps.data ?? []).length === 0 ? <EmptyState icon="🤖" title="아직 매칭된 자동화 제안이 없어요" hint="뉴스·작업정의가 쌓이면 표시됩니다." />
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

      {/* ⑤ 내 키워드 + 수집 */}
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
