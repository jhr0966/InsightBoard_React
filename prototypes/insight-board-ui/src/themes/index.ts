/**
 * Theme Registry — 프리셋 추가/삭제의 유일한 진입점.
 *
 * 새 프리셋을 추가하려면:
 *   1. presets/<name>.ts 에 ThemeTokens 객체 export
 *   2. 아래 import 한 줄 + THEMES 배열에 한 칸 추가
 *   3. 끝. ThemeProvider · 설정 화면은 자동으로 그것을 노출한다.
 *
 * 삭제도 같은 두 줄만 지우면 된다.
 */
import type { ThemeTokens } from './types';
import { midnight } from './presets/midnight';
import { forest } from './presets/forest';
import { plum } from './presets/plum';
import { slate } from './presets/slate';

export const THEMES: readonly ThemeTokens[] = [
  midnight,
  forest,
  plum,
  slate,
] as const;

/** 첫 진입 / localStorage 미설정 시 사용할 기본 테마 id */
export const DEFAULT_THEME_ID = midnight.id;

/** localStorage 키 — 다른 영속화 키와 충돌 없도록 한 곳에서 관리 */
export const THEME_STORAGE_KEY = 'insight-board:theme';

export type ThemeId = (typeof THEMES)[number]['id'];

export function getThemeById(id: string): ThemeTokens {
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}

export type { ThemeTokens } from './types';
export { TOKEN_CSS_VARS } from './types';
