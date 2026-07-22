import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { navByPath } from "../nav";
import { clickableProps } from "./ui";

// 상단바 — 브레드크럼·제목·갱신시각·알림벨·설정·아바타·전역검색 (ui/app_shell.py 승계).
export default function Topbar({
  pathname,
  onSearch,
  onMenu,
}: {
  pathname: string;
  onSearch: (q: string) => void;
  onMenu: () => void;
}) {
  const nav = navByPath(pathname);
  const navigate = useNavigate();
  const summary = useQuery({
    queryKey: ["proposals", "summary"],
    queryFn: () => api.proposals.summary(),
  });
  const llm = useQuery({ queryKey: ["assistant", "status"], queryFn: () => api.assistant.status() });
  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const today = useQuery({ queryKey: ["news", "today"], queryFn: () => api.news.today() });
  const pendingAdopt = summary.data?.reviewing ?? 0;

  const now = new Date();
  const stamp = `${now.getMonth() + 1}.${now.getDate()} · ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")} 갱신`;

  // 신선도 — 오늘 수집 중 최신 collected_at 기준(FRESH/최신/오래됨).
  const latestTs = (today.data ?? [])
    .map((a) => Date.parse(a.collected_at || a.published_at || a.date || ""))
    .filter((t) => !Number.isNaN(t)).sort((a, b) => b - a)[0];
  const ageH = latestTs ? (Date.now() - latestTs) / 3.6e6 : Infinity;
  const fresh = ageH <= 6 ? { label: "실시간", cls: "topbar-fresh-accent" }
    : ageH <= 24 ? { label: "최신", cls: "topbar-fresh-accent" }
    : Number.isFinite(ageH) ? { label: "오래됨", cls: "topbar-fresh-warn" }
    : { label: "수집 전", cls: "" };

  // 아바타 — 페르소나 이름/부서 첫 글자.
  const avatar = (persona.data?.name?.trim()?.[0] || persona.data?.dept?.trim()?.[0] || "?");

  return (
    <>
    {llm.data && !llm.data.configured && (
      <div className="topbar-banner" role="status">
        ⚠️ LLM(SOLA)이 설정되지 않았어요 — 제안서·요약·채팅이 제한됩니다.
        <span className="muted"> 백엔드 환경변수 LLM_API_KEY·LLM_MODEL 을 설정하세요.</span>
      </div>
    )}
    <header className="topbar">
      <div className="topbar-l">
        {/* 햄버거 — 모바일에서만 노출(CSS). 좌측 사이드바 오프캔버스 토글. */}
        <button className="topbar-menu" title="메뉴" onClick={onMenu} aria-label="메뉴 열기">☰</button>
        <div className="topbar-eye">
          WORKFLOW <span className="topbar-eye-sep">/</span>{" "}
          <span className="topbar-eye-cur">{nav.name}</span>
        </div>
        <div className="topbar-title-row">
          <h1 className="topbar-title">{nav.emoji} {nav.name}</h1>
          <span className="topbar-date"><span className="topbar-date-dot" />{stamp}</span>
          <span className={`topbar-fresh ${fresh.cls}`}>{fresh.label}</span>
        </div>
      </div>

      <div className="topbar-r">
        <input
          className="topbar-search"
          placeholder="🔎 뉴스 키워드 검색 — Enter"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onSearch((e.target as HTMLInputElement).value);
              navigate("/feed");
            }
          }}
        />
        <button
          className="topbar-btn"
          title={pendingAdopt > 0 ? `${pendingAdopt}건 검토 중` : "새 알림 없음"}
          aria-label={pendingAdopt > 0 ? `알림 — ${pendingAdopt}건 검토 중` : "알림 — 새 알림 없음"}
          onClick={() => navigate("/proposals")}
        >
          🔔{pendingAdopt > 0 && <span className="topbar-dot-badge">{pendingAdopt}</span>}
        </button>
        <button className="topbar-btn" title="설정 · 프로필" aria-label="설정 · 프로필" onClick={() => navigate("/persona")}>⚙</button>
        <div className="topbar-avatar" title={persona.data?.name || "프로필"}
          {...clickableProps(() => navigate("/persona"), "프로필 · 페르소나 열기")} style={{ cursor: "pointer" }}>{avatar}</div>
      </div>
    </header>
    </>
  );
}
