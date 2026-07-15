// 네비게이션 단일 소스 — Sidebar · Topbar 가 공유.
// Step 11 IA 재편: "부담 없이 읽는 층"(오늘·뉴스 탐색·자동화 과제)과
// "필요할 때 파고드는 층"(분석실), "운영 층"(수집 관리·작업 정의)을 분리.
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
  { to: "/", emoji: "📊", name: "오늘", sub: "맞춤 다이제스트", num: 1, end: true, screen: "board", label: "📊 오늘" },
  { to: "/feed", emoji: "🗞", name: "뉴스 탐색", sub: "전체 기사 · 검색", num: 2, screen: "feed", label: "🗞 뉴스 탐색" },
  { to: "/proposals", emoji: "🤖", name: "자동화 과제", sub: "제안 생성 · 보관함", num: 3, screen: "proposals", label: "🤖 자동화 과제" },
  { to: "/insights", emoji: "🔎", name: "분석실", sub: "트렌드 · 매트릭스 · 히트맵", num: 4, screen: "insights", label: "🔎 분석실" },
];

export const NAV_MANAGE: NavItem[] = [
  { to: "/collect", emoji: "⚙️", name: "수집 관리", sub: "수집 실행 · 출처 · 진단", num: 5, screen: "collect", label: "⚙️ 수집 관리" },
  { to: "/taskdefs", emoji: "📋", name: "작업 정의", sub: "엑셀 업로드 · 정의 관리", num: 6, screen: "taskdefs", label: "📋 작업 정의" },
];

export const NAV_ALL: NavItem[] = [...NAV_MAIN, ...NAV_MANAGE];

export const SCREEN_BY_PATH: Record<string, string> = Object.fromEntries(
  NAV_ALL.map((n) => [n.to, n.screen]),
);

export function navByPath(pathname: string): NavItem {
  return NAV_ALL.find((n) => n.to === pathname) ?? NAV_MAIN[0];
}
