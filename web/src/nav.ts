// 네비게이션 단일 소스 — Sidebar · CommandPalette · Topbar 가 공유.
// 현행 ui/sidebar.py 의 _MAIN_AREAS / _MANAGE_AREAS 그룹 + 번호 계승.
export interface NavItem {
  to: string;
  label: string;
  emoji: string;
  name: string;
  sub: string;
  num: number;
  end?: boolean;
  screen: string;
}

export const NAV_MAIN: NavItem[] = [
  { to: "/", emoji: "📊", name: "오늘의 보드", sub: "맞춤 인사이트", num: 1, end: true, screen: "board", label: "📊 오늘의 보드" },
  { to: "/insights", emoji: "🔎", name: "인사이트 분석", sub: "트렌드 · 기회 · 매칭", num: 2, screen: "insights", label: "🔎 인사이트 분석" },
  { to: "/proposals", emoji: "🤖", name: "자동화 제안", sub: "제안 생성 · 대화", num: 3, screen: "proposals", label: "🤖 자동화 제안" },
];

export const NAV_MANAGE: NavItem[] = [
  { to: "/collect", emoji: "🗞", name: "뉴스 수집", sub: "수집 · 보관 · 설정", num: 4, screen: "collect", label: "🗞 뉴스 수집" },
  { to: "/taskdefs", emoji: "📋", name: "작업 정의", sub: "엑셀 업로드 · 정의 관리", num: 5, screen: "taskdefs", label: "📋 작업 정의" },
];

export const NAV_ALL: NavItem[] = [...NAV_MAIN, ...NAV_MANAGE];

export const SCREEN_BY_PATH: Record<string, string> = Object.fromEntries(
  NAV_ALL.map((n) => [n.to, n.screen]),
);

export function navByPath(pathname: string): NavItem {
  return NAV_ALL.find((n) => n.to === pathname) ?? NAV_MAIN[0];
}
