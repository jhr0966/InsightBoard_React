import type { ThemeTokens } from '../types';

/**
 * Slate — neutral gray + blue.
 * 가장 중립적인 무광 톤. 장시간 작업·문서 검토용.
 */
export const slate: ThemeTokens = {
  id: 'slate',
  label: 'Slate',
  description: 'Neutral gray with blue accent — 무광 중립',

  background: {
    base: '#0E1116',
    gradientFrom: '#161B23',
    gradientTo: '#070A0E',
    orb1: 'rgba(96, 165, 250, 0.16)',
    orb2: 'rgba(148, 163, 184, 0.12)',
    noiseOpacity: '0.05',
  },

  surface: {
    glassBg: 'rgba(255, 255, 255, 0.04)',
    glassBorder: 'rgba(255, 255, 255, 0.07)',
    glassShadow: '0 8px 32px rgba(0, 0, 0, 0.40), 0 2px 6px rgba(0, 0, 0, 0.20)',
    glassHighlight: 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    glassBgElevated: 'rgba(255, 255, 255, 0.06)',
  },

  text: {
    primary: '#E8ECF2',
    secondary: '#A4ACB9',
    muted: '#6A7281',
    onAccent: '#0A0F14',
  },

  accent: {
    primary: '#60A5FA',
    hover: '#93C5FD',
    active: '#3B82F6',
    soft: 'rgba(96, 165, 250, 0.12)',
  },

  semantic: {
    success: '#34D399',
    warning: '#FBBF24',
    danger: '#F87171',
    info: '#60A5FA',
  },

  chart: {
    series1: '#60A5FA',
    series2: '#94A3B8',
    series3: '#34D399',
    series4: '#FBBF24',
    series5: '#F87171',
    series6: '#A78BFA',
  },
};
