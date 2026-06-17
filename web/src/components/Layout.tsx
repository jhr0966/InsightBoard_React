import { useEffect, useState } from "react";
import { Outlet, useLocation, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AssistantDrawer from "./AssistantDrawer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import Onboarding, { shouldOnboard } from "./Onboarding";
import { SCREEN_BY_PATH } from "../nav";
import { useGlobalSearch } from "../search";
import { api } from "../api/client";

export default function Layout() {
  // 채팅 드로어 — 기본 펼침. 사용자가 닫으면 localStorage 로 기억.
  const [drawerOpen, setDrawerOpen] = useState(() => localStorage.getItem("sola.drawer") !== "closed");
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";

  // 인계(?from=)로 들어오면 SOLA 드로어를 자동으로 펼친다(자동 검토를 보이게).
  // 사용자 명시적 닫기 선호(localStorage)는 덮어쓰지 않도록 transient open 만.
  useEffect(() => {
    if (params.get("from")) setDrawerOpen(true);
  }, [params]);
  const { setQuery } = useGlobalSearch();
  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const [onbClosed, setOnbClosed] = useState(false);
  const showOnb = !onbClosed && shouldOnboard(persona.data?.is_set);

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

      {showOnb && <Onboarding onClose={() => setOnbClosed(true)} />}
    </div>
  );
}
