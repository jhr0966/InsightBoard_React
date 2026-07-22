import { useQuery } from "@tanstack/react-query";
import { NavLink, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { NAV_MAIN, NAV_MANAGE } from "../nav";
import ThemeSwitcher from "./ThemeSwitcher";

function NavRow({ to, emoji, num, name, sub, end }: (typeof NAV_MAIN)[number]) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
      <span className="nav-item-num">{num}</span>
      <span className="nav-item-body">
        <strong>{emoji} {name}</strong>
        <span className="nav-item-sub">{sub}</span>
      </span>
    </NavLink>
  );
}

// 좌측 사이드바 — 브랜드·페르소나 카드·통계·그룹 nav·LLM 상태 (ui/sidebar.py 승계).
export default function Sidebar() {
  // 과제 통계는 Proposal 엔터티 summary 로(과거엔 bookmark 요약의 pending 을 읽어
  // 항상 0 이었다 — 상태 9종 개편 후 pending 상태가 없어졌기 때문).
  const summary = useQuery({ queryKey: ["proposals", "summary"], queryFn: () => api.proposals.summary() });
  const llm = useQuery({ queryKey: ["assistant", "status"], queryFn: () => api.assistant.status() });
  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const navigate = useNavigate();

  const by = summary.data?.by_status ?? {};
  const total = summary.data?.total ?? 0;
  const adopted = summary.data?.adopted ?? 0;
  const reviewing = (by.reviewing ?? 0) + (by.feasibility ?? 0);  // 검토·평가 단계 합계

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-logo">📊</div>
        <div className="sidebar-brand-copy">
          <div className="sidebar-brand-text">Insight<strong>Board</strong></div>
          <div className="sidebar-brand-tag">조선소 작업 인사이트</div>
        </div>
      </div>

      <div className="persona-card" onClick={() => navigate("/persona")}>
        {persona.data?.is_set ? (
          <>
            <div className="persona-head">{(persona.data.name || persona.data.dept || "?").slice(0, 1)}</div>
            <div>
              <div className="persona-name">{persona.data.name || persona.data.dept}</div>
              <div className="muted">{persona.data.label}</div>
            </div>
          </>
        ) : (
          <>
            <div className="persona-head-empty">👤</div>
            <div>
              <div className="persona-name">페르소나 미설정</div>
              <div className="muted">설정에서 시작하세요</div>
            </div>
          </>
        )}
      </div>

      <div className="sidebar-stats">
        <div><b>{total}</b><span className="muted">과제</span></div>
        <div><b>{adopted}</b><span className="muted">채택</span></div>
        <div><b>{reviewing}</b><span className="muted">검토 중</span></div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">워크플로</div>
        {NAV_MAIN.map((n) => <NavRow key={n.to} {...n} />)}
        <div className="sidebar-section-label">관리</div>
        {NAV_MANAGE.map((n) => <NavRow key={n.to} {...n} />)}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <ThemeSwitcher />
        <div className="sidebar-llm">
          <span className={`sidebar-dot ${llm.data?.configured ? "ok" : "warn"}`} />
          LLM · {llm.data?.provider ?? "…"}
          {llm.data && !llm.data.configured && <span className="muted"> · 키 미설정</span>}
        </div>
      </div>
    </aside>
  );
}
