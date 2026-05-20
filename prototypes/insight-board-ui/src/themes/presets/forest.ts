import type { ThemeTokens } from '../types';

/**
 * Forest — dark green + amber.
 * 자연/현장 무드. 야적장·드라이독의 안정감.
 */
export const forest: ThemeTokens = {
  id: 'forest',
  label: 'Forest',
  description: 'Dark green base with amber accent — 현장의 안정감',

  background: {
    base: '#08120D',
    gradientFrom: '#0C1F16',
    gradientTo: '#040A07',
    orb1: 'rgba(52, 211, 153, 0.20)',
    orb2: 'rgba(251, 191, 36, 0.14)',
    noiseOpacity: '0.04',
  },

  surface: {
    glassBg: 'rgba(255, 255, 255, 0.04)',
    glassBorder: 'rgba(190, 215, 200, 0.10)',
    glassShadow: '0 10px 40px rgba(0, 0, 0, 0.45), 0 2px 8px rgba(0, 0, 0, 0.25)',
    glassHighlight: 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    glassBgElevated: 'rgba(255, 255, 255, 0.065)',
  },

  text: {
    primary: '#F0F5F1',
    secondary: '#B5C6BB',
    muted: '#6A8175',
    onAccent: '#0F1A09',
  },

  accent: {
    primary: '#FBBF24',
    hover: '#FCD34D',
    active: '#F59E0B',
    soft: 'rgba(251, 191, 36, 0.14)',
  },

  semantic: {
    success: '#34D399',
    warning: '#FBBF24',
    danger: '#F87171',
    info: '#7DD3FC',
  },

  chart: {
    series1: '#34D399',
    series2: '#FBBF24',
    series3: '#7DD3FC',
    series4: '#F87171',
    series5: '#A3E635',
    series6: '#C084FC',
  },
};
