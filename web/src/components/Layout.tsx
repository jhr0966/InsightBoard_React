import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import AssistantDrawer from "./AssistantDrawer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { SCREEN_BY_PATH } from "../nav";
import { useGlobalSearch } from "../search";

export default function Layout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { pathname } = useLocation();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";
  const { setQuery } = useGlobalSearch();

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
        <AssistantDrawer screen={screen} onClose={() => setDrawerOpen(false)} />
      ) : (
        <button className="btn primary drawer-toggle" onClick={() => setDrawerOpen(true)}>
          💬 SOLA
        </button>
      )}
    </div>
  );
}
