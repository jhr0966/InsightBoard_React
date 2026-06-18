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
  // 채팅 드로어 — 명시적 선호(localStorage) 우선, 없으면 넓은 화면만 펼침.
  // (좁은 화면은 드로어가 오버레이라 첫 방문에 본문을 가리지 않게 접어 둔다.)
  const [drawerOpen, setDrawerOpen] = useState(() => {
    const pref = localStorage.getItem("sola.drawer");
    if (pref) return pref === "open";
    return typeof window !== "undefined" ? window.innerWidth > 1100 : true;
  });
  // 모바일 사이드바 오프캔버스 — 기본 닫힘(좁은 화면에서만 햄버거로 연다).
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const screen = SCREEN_BY_PATH[pathname] ?? "board";

  // 인계(?from=)로 들어오면 SOLA 드로어를 자동으로 펼친다(자동 검토를 보이게).
  // 사용자 명시적 닫기 선호(localStorage)는 덮어쓰지 않도록 transient open 만.
  useEffect(() => {
    if (params.get("from")) setDrawerOpen(true);
  }, [params]);
  // 화면(라우트) 이동 시 모바일 사이드바는 자동으로 닫는다(오프캔버스가 남지 않게).
  useEffect(() => { setSidebarOpen(false); }, [pathname]);
  const { setQuery } = useGlobalSearch();
  const persona = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const [onbClosed, setOnbClosed] = useState(false);
  const showOnb = !onbClosed && shouldOnboard(persona.data?.is_set);

  function setDrawer(open: boolean) {
    setDrawerOpen(open);
    localStorage.setItem("sola.drawer", open ? "open" : "closed");
  }

  return (
    <div className={`shell${drawerOpen ? " drawer-open" : ""}${sidebarOpen ? " sidebar-open" : ""}`}>
      <Sidebar />

      <div className="shell-main">
        <Topbar pathname={pathname} onSearch={setQuery} onMenu={() => setSidebarOpen((v) => !v)} />
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

      {/* 모바일 오프캔버스 백드롭 — 사이드바 열렸을 때만. 클릭 시 닫기. */}
      {sidebarOpen && <div className="nav-backdrop" onClick={() => setSidebarOpen(false)} />}

      {showOnb && <Onboarding onClose={() => setOnbClosed(true)} />}
    </div>
  );
}
