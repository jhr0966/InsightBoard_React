import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { navByPath } from "../nav";

// 상단바 — 브레드크럼·제목·갱신시각·알림벨·설정·아바타·전역검색 (ui/app_shell.py 승계).
export default function Topbar({
  pathname,
  onSearch,
}: {
  pathname: string;
  onSearch: (q: string) => void;
}) {
  const nav = navByPath(pathname);
  const navigate = useNavigate();
  const summary = useQuery({
    queryKey: ["bookmarks", "summary"],
    queryFn: () => api.bookmarks.summary(),
  });
  const pendingAdopt =
    ((summary.data?.proposal_status as Record<string, number> | undefined)?.pending) ?? 0;

  const now = new Date();
  const stamp = `${now.getMonth() + 1}.${now.getDate()} · ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")} 갱신`;

  return (
    <header className="topbar">
      <div className="topbar-l">
        <div className="topbar-eye">
          WORKFLOW <span className="topbar-eye-sep">/</span>{" "}
          <span className="topbar-eye-cur">{nav.name}</span>
        </div>
        <div className="topbar-title-row">
          <h1 className="topbar-title">{nav.emoji} {nav.name}</h1>
          <span className="topbar-date"><span className="topbar-date-dot" />{stamp}</span>
          <span className="topbar-fresh topbar-fresh-accent">LIVE</span>
        </div>
      </div>

      <div className="topbar-r">
        <input
          className="topbar-search"
          placeholder="🔎 뉴스 키워드 검색 — Enter"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onSearch((e.target as HTMLInputElement).value);
              navigate("/collect");
            }
          }}
        />
        <button
          className="topbar-btn"
          title={pendingAdopt > 0 ? `${pendingAdopt}건 채택 대기` : "새 알림 없음"}
          onClick={() => navigate("/proposals")}
        >
          🔔{pendingAdopt > 0 && <span className="topbar-dot-badge">{pendingAdopt}</span>}
        </button>
        <button className="topbar-btn" title="설정 · 프로필" onClick={() => navigate("/proposals")}>⚙</button>
        <div className="topbar-avatar">?</div>
      </div>
    </header>
  );
}
