import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import AssistantDrawer from "./AssistantDrawer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { SCREEN_BY_PATH } from "../nav";
import { useGlobalSearch } from "../search";

export default function Layout() {
  // 채팅 드로어 — 기본 펼침. 사용자가 닫으면 localStorage 로 기억.
  const [drawerOpen, setDrawerOpen] = useState(() => localStorage.getItem("sola.drawer") !== "closed");
  const { pathname } = useLocation();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";
  const { setQuery } = useGlobalSearch();

  function setDrawer(open: boolean) {
    setDrawerOpen(open);
    localStorage.setItem("sola.drawer", open ? "open" : "closed");
  }

  return (
    <div className={`shell${drawerOpen ? " drawer-open" : ""}`}>
      <Sidebar />

      <div className="shell-main">
        <Topbar pathname={pathname} onSearch={setQuery} />
        <main className="main">
          <Outlet />
        </main>
      </div>

      {drawerOpen ? (
        <AssistantDrawer screen={screen} onClose={() => setDrawer(false)} />
      ) : (
        <button className="btn primary drawer-toggle" onClick={() => setDrawer(true)}>
          💬 SOLA
        </button>
      )}
    </div>
  );
}
