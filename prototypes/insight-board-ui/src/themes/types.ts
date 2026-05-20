/**
 * ThemeTokens — 인사이트보드 전체 컬러·표면·차트 토큰의 단일 정의.
 *
 * 모든 프리셋은 이 타입을 만족해야 하고, ThemeProvider 는 이 객체를 평탄화해
 * `:root` 의 CSS Custom Properties 로 주입한다. 컴포넌트는 오로지 `var(--token)`
 * 만 참조한다 — 프리셋 추가/삭제는 `themes/index.ts` 한 곳에서 끝나야 한다.
 */
export interface ThemeTokens {
  /** 내부 식별자 (kebab-case). localStorage 키로도 쓰임 */
  readonly id: string;
  /** 설정 화면에 노출되는 사람이 읽는 이름 */
  readonly label: string;
  /** 한 줄 설명 — 프리뷰 카드 부제목으로 사용 */
  readonly description: string;

  readonly background: {
    /** body 의 base 색 (그라데이션이 안 들어오는 영역의 fallback) */
    base: string;
    /** body 그라데이션 시작 (좌상단) */
    gradientFrom: string;
    /** body 그라데이션 종료 (우하단) */
    gradientTo: string;
    /** 좌상단 abstract orb — rgba 권장 (블러로 번질 색) */
    orb1: string;
    /** 우하단 abstract orb */
    orb2: string;
    /** noise 오버레이 강도 (0~1). CSS opacity 로 직결 */
    noiseOpacity: string;
  };

  readonly surface: {
    /** Glass 카드 본체 — 매우 옅은 흰색/유색 rgba */
    glassBg: string;
    /** Glass 카드 테두리 — 1px hairline */
    glassBorder: string;
    /** Glass 카드 드롭섀도우 (전체 box-shadow 문자열) */
    glassShadow: string;
    /** Glass 카드 하이라이트(상단 inner border) — box-shadow inset 으로 합성 */
    glassHighlight: string;
    /** elevated 변형 (모달/팝오버) */
    glassBgElevated: string;
  };

  readonly text: {
    primary: string;
    secondary: string;
    muted: string;
    /** 액센트 위의 텍스트 (버튼 등) */
    onAccent: string;
  };

  readonly accent: {
    primary: string;
    hover: string;
    active: string;
    /** 액센트의 옅은 배경 (chip, soft button) */
    soft: string;
  };

  readonly semantic: {
    success: string;
    warning: string;
    danger: string;
    info: string;
  };

  /** 데이터 시각화용 시리즈 컬러 — 6개 고정 */
  readonly chart: {
    series1: string;
    series2: string;
    series3: string;
    series4: string;
    series5: string;
    series6: string;
  };
}

/**
 * 토큰 트리를 CSS Custom Property 이름으로 평탄화한 키 맵.
 * ThemeProvider 는 이 맵의 키를 순회하며 `style.setProperty(value, theme[path])` 한다.
 *
 * 형식: 점 표기 path → `--token-...` 이름.
 */
export const TOKEN_CSS_VARS = {
  'background.base': '--bg-base',
  'background.gradientFrom': '--bg-gradient-from',
  'background.gradientTo': '--bg-gradient-to',
  'background.orb1': '--bg-orb-1',
  'background.orb2': '--bg-orb-2',
  'background.noiseOpacity': '--bg-noise-opacity',

  'surface.glassBg': '--surface-glass-bg',
  'surface.glassBorder': '--surface-glass-border',
  'surface.glassShadow': '--surface-glass-shadow',
  'surface.glassHighlight': '--surface-glass-highlight',
  'surface.glassBgElevated': '--surface-glass-bg-elevated',

  'text.primary': '--text-primary',
  'text.secondary': '--text-secondary',
  'text.muted': '--text-muted',
  'text.onAccent': '--text-on-accent',

  'accent.primary': '--accent-primary',
  'accent.hover': '--accent-hover',
  'accent.active': '--accent-active',
  'accent.soft': '--accent-soft',

  'semantic.success': '--semantic-success',
  'semantic.warning': '--semantic-warning',
  'semantic.danger': '--semantic-danger',
  'semantic.info': '--semantic-info',

  'chart.series1': '--chart-1',
  'chart.series2': '--chart-2',
  'chart.series3': '--chart-3',
  'chart.series4': '--chart-4',
  'chart.series5': '--chart-5',
  'chart.series6': '--chart-6',
} as const;

export type TokenPath = keyof typeof TOKEN_CSS_VARS;

/**
 * 점 표기 path 로 ThemeTokens 객체에서 값을 꺼낸다.
 * (ThemeProvider 내부 전용 — 외부 컴포넌트는 var(--token) 만 쓴다.)
 */
export function readTokenValue(theme: ThemeTokens, path: TokenPath): string {
  const [group, key] = path.split('.') as [keyof ThemeTokens, string];
  const groupObj = theme[group] as Record<string, string>;
  return groupObj[key];
}
