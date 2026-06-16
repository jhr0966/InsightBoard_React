import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import AssistantDrawer from "./AssistantDrawer";
import CommandPalette from "./CommandPalette";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { SCREEN_BY_PATH } from "../nav";
import { useGlobalSearch } from "../search";

export default function Layout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { pathname } = useLocation();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";
  const { setQuery } = useGlobalSearch();

  // ⌘K / Ctrl+K → 팔레트
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className={`shell${drawerOpen ? " drawer-open" : ""}`}>
      <Sidebar />

      <div className="shell-main">
        <Topbar pathname={pathname} onSearch={setQuery} onOpenPalette={() => setPaletteOpen(true)} />
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

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
