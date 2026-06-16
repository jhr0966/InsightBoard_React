import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import AssistantDrawer from "./AssistantDrawer";
import ThemeSwitcher from "./ThemeSwitcher";

const NAV = [
  { to: "/", label: "📊 오늘의 보드", end: true, screen: "board" },
  { to: "/insights", label: "🔎 인사이트 분석", screen: "insights" },
  { to: "/proposals", label: "🤖 자동화 제안", screen: "proposals" },
  { to: "/collect", label: "🗞 뉴스 수집", screen: "collect" },
  { to: "/taskdefs", label: "📋 작업 정의", screen: "taskdefs" },
];

const SCREEN_BY_PATH: Record<string, string> = {
  "/": "board",
  "/insights": "insights",
  "/proposals": "proposals",
  "/collect": "collect",
  "/taskdefs": "taskdefs",
};

export default function Layout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { pathname } = useLocation();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";

  return (
    <div className={`shell${drawerOpen ? " drawer-open" : ""}`}>
      <aside className="sidebar">
        <div className="brand">인사이트보드</div>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            {n.label}
          </NavLink>
        ))}
        <div style={{ marginTop: "auto" }}>
          <ThemeSwitcher />
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>

      {drawerOpen ? (
        <AssistantDrawer screen={screen} onClose={() => setDrawerOpen(false)} />
      ) : (
        <button className="btn primary drawer-toggle" onClick={() => setDrawerOpen(true)}>
          💬 SOLA
        </button>
      )}
    </div>
  );
}
