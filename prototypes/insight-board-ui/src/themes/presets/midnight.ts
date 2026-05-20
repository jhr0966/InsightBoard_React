import type { ThemeTokens } from '../types';

/**
 * Midnight — deep navy + cyan.
 * 기본 테마. 조선·해양 도메인의 깊이감, 야간 함교(brige) 무드.
 */
export const midnight: ThemeTokens = {
  id: 'midnight',
  label: 'Midnight',
  description: 'Deep navy with cyan orbs — 기본 야간 함교 무드',

  background: {
    base: '#070B16',
    gradientFrom: '#0B1430',
    gradientTo: '#04060F',
    orb1: 'rgba(56, 189, 248, 0.22)',
    orb2: 'rgba(99, 102, 241, 0.18)',
    noiseOpacity: '0.035',
  },

  surface: {
    glassBg: 'rgba(255, 255, 255, 0.045)',
    glassBorder: 'rgba(255, 255, 255, 0.08)',
    glassShadow: '0 10px 40px rgba(0, 0, 0, 0.45), 0 2px 8px rgba(0, 0, 0, 0.25)',
    glassHighlight: 'inset 0 1px 0 rgba(255, 255, 255, 0.06)',
    glassBgElevated: 'rgba(255, 255, 255, 0.07)',
  },

  text: {
    primary: '#F1F5FB',
    secondary: '#B6C2DA',
    muted: '#6E7B98',
    onAccent: '#06121E',
  },

  accent: {
    primary: '#38BDF8',
    hover: '#67D4F9',
    active: '#0EA5E9',
    soft: 'rgba(56, 189, 248, 0.14)',
  },

  semantic: {
    success: '#34D399',
    warning: '#FBBF24',
    danger: '#F87171',
    info: '#60A5FA',
  },

  chart: {
    series1: '#38BDF8',
    series2: '#818CF8',
    series3: '#34D399',
    series4: '#FBBF24',
    series5: '#F472B6',
    series6: '#A78BFA',
  },
};
