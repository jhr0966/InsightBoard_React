import type { ThemeTokens } from '../types';

/**
 * Plum — deep purple + pink.
 * 인사이트·창의 무드. 야간 보랏빛 노을.
 */
export const plum: ThemeTokens = {
  id: 'plum',
  label: 'Plum',
  description: 'Deep purple with pink orbs — 야간 노을',

  background: {
    base: '#0F0820',
    gradientFrom: '#1B0E35',
    gradientTo: '#06030E',
    orb1: 'rgba(168, 85, 247, 0.22)',
    orb2: 'rgba(244, 114, 182, 0.16)',
    noiseOpacity: '0.04',
  },

  surface: {
    glassBg: 'rgba(255, 255, 255, 0.05)',
    glassBorder: 'rgba(214, 196, 255, 0.10)',
    glassShadow: '0 10px 40px rgba(15, 8, 32, 0.55), 0 2px 8px rgba(0, 0, 0, 0.3)',
    glassHighlight: 'inset 0 1px 0 rgba(255, 255, 255, 0.07)',
    glassBgElevated: 'rgba(255, 255, 255, 0.075)',
  },

  text: {
    primary: '#F4EEFB',
    secondary: '#C7B8E0',
    muted: '#7E6F95',
    onAccent: '#1A0A2E',
  },

  accent: {
    primary: '#F472B6',
    hover: '#F9A8D4',
    active: '#EC4899',
    soft: 'rgba(244, 114, 182, 0.16)',
  },

  semantic: {
    success: '#34D399',
    warning: '#FCD34D',
    danger: '#FB7185',
    info: '#A78BFA',
  },

  chart: {
    series1: '#F472B6',
    series2: '#A78BFA',
    series3: '#67E8F9',
    series4: '#FCD34D',
    series5: '#FB7185',
    series6: '#C4B5FD',
  },
};
