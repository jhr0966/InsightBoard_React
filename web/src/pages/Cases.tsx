import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Badge, EmptyState, Tabs, LoadError } from "../components/ui";
import { useToast } from "../components/ui/toast";

// 적용 사례 라이브러리 (Step 12) — 뉴스에서 정제된 AI·자동화 사례 자산.
// 상태: pending_review(자동 추출) → approved / excluded. 승인 사례만 제안서 주근거.
const STATUS_LABEL: Record<string, { label: string; tone: "warning" | "success" | "default" }> = {
  pending_review: { label: "검토 대기", tone: "warning" },
  approved: { label: "승인", tone: "success" },
  excluded: { label: "제외", tone: "default" },
};

export default function Cases() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState<string>("all");

  const cases = useQuery({
    queryKey: ["cases", status],
    queryFn: () => api.cases.list(status === "all" ? undefined : status),
  });
  const summary = useQuery({ queryKey: ["cases", "summary"], queryFn: () => api.cases.summary() });
  const setCaseStatus = useMutation({
    mutationFn: ({ id, s }: { id: string; s: string }) => api.cases.setStatus(id, s),
    onSuccess: (_d, v) => {
      const msg = v.s === "approved" ? "✅ 승인 — 이제 제안서 근거로 쓰여요"
        : v.s === "excluded" ? "제외했어요"
        : v.s === "pending_review" ? "검토 대기로 되돌렸어요" : "처리했어요";
      toast.push(msg, "success");
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });
  const extract = useMutation({
    mutationFn: () => api.cases.extract(),
    onSuccess: (d) => {
      toast.push(d.extracted ? `🧠 사례 ${d.extracted}건 추출` : (d.reason ?? "새 사례 없음"), d.extracted ? "success" : "default");
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (e) => toast.push((e as Error).message, "danger"),
  });

  const by = summary.data?.by_status ?? {};
  const items = cases.data ?? [];
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <Tabs value={status} onChange={setStatus} items={[
          { key: "all", label: `전체 ${summary.data?.total ?? ""}` },
          { key: "pending_review", label: `검토 대기 ${by.pending_review ?? 0}` },
          { key: "approved", label: `승인 ${by.approved ?? 0}` },
          { key: "excluded", label: `제외 ${by.excluded ?? 0}` },
        ]} />
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={extract.isPending} onClick={() => extract.mutate()}>
          {extract.isPending ? "추출 중…" : "🧠 최근 기사에서 사례 추출"}</button>
      </div>

      {cases.isLoading ? <div className="bd-grid">{[0, 1, 2].map((i) => <div key={i} className="skel skel-card" />)}</div>
        : cases.isError ? <LoadError message="사례를 불러오지 못했어요" onRetry={() => cases.refetch()} />
        : items.length === 0 ? (
          <EmptyState icon="📚" title="아직 사례가 없어요"
            hint="수집이 쌓이면 매일 자동 추출됩니다. '최근 기사에서 사례 추출'로 바로 시작할 수도 있어요." />
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {items.map((c) => {
              const st = STATUS_LABEL[c.review_status] ?? STATUS_LABEL.pending_review;
              return (
                <div className="card" key={c.case_id} style={{ margin: 0, display: "grid", gap: 6 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontWeight: 600, lineHeight: 1.4, flex: 1 }}>{c.title}</span>
                    <Badge tone={st.tone}>{st.label}</Badge>
                  </div>
                  <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>
                    {[c.industry, c.target_work, c.implementation].filter(Boolean).join(" · ")}
                  </div>
                  {c.problem && <div style={{ fontSize: "var(--fs-caption)", lineHeight: 1.6 }}>
                    <b>문제</b> {c.problem}</div>}
                  {c.solution && <div style={{ fontSize: "var(--fs-caption)", lineHeight: 1.6 }}>
                    <b>해법</b> {c.solution}</div>}
                  {(c.quantified_effects ?? []).slice(0, 2).map((e, i) => (
                    <div key={i} style={{ fontSize: "var(--fs-caption)" }}>
                      📈 {e.metric} <b>{e.value}</b>
                      {e.evidence_text && <span className="muted"> — “{e.evidence_text}”</span>}
                    </div>
                  ))}
                  {c.shipyard_implications && (
                    <div style={{ fontSize: "var(--fs-caption)", lineHeight: 1.6 }}>
                      🏗 <b>조선소 접목</b> {c.shipyard_implications}
                      <span className="muted" style={{ fontSize: "var(--fs-micro)" }}> (시스템 유추)</span>
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                    <span className="muted" style={{ fontSize: "var(--fs-micro)", marginRight: "auto" }}>
                      신뢰도 {(c.confidence * 100).toFixed(0)}%
                      {(c.sources ?? []).map((s) => (
                        <a key={s.article_id} href={s.link} target="_blank" rel="noreferrer noopener"
                          style={{ marginLeft: 8 }}>원문 ↗</a>
                      ))}
                    </span>
                    {c.review_status !== "approved" &&
                      <button className="oa-mini" onClick={() => setCaseStatus.mutate({ id: c.case_id, s: "approved" })}>✅ 승인</button>}
                    {c.review_status !== "excluded" &&
                      <button className="oa-mini" onClick={() => setCaseStatus.mutate({ id: c.case_id, s: "excluded" })}>제외</button>}
                    {c.review_status !== "pending_review" &&
                      <button className="oa-mini" onClick={() => setCaseStatus.mutate({ id: c.case_id, s: "pending_review" })}>↶ 대기로</button>}
                    <button className="oa-mini" onClick={() => nav(`/proposals?from=case&case_id=${encodeURIComponent(c.case_id)}&work=${encodeURIComponent(c.target_work || c.title)}`)}>이 사례로 제안서 →</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
    </div>
  );
}
