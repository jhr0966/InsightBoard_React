import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

// 표시 설정 — store/ui_prefs.py 승계 (테마 4종 · 글자 3단).
export const THEMES = ["light", "dark", "ocean", "sunset"] as const;
export const FONTS = ["small", "medium", "large"] as const;
export type Theme = (typeof THEMES)[number];
export type Font = (typeof FONTS)[number];

interface ThemeState {
  theme: Theme;
  font: Font;
  setTheme: (t: Theme) => void;
  setFont: (f: Font) => void;
}

const KEY = "insightboard.prefs";
const DEFAULTS: { theme: Theme; font: Font } = { theme: "light", font: "medium" };

function load(): { theme: Theme; font: Font } {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    return {
      theme: THEMES.includes(raw.theme) ? raw.theme : DEFAULTS.theme,
      font: FONTS.includes(raw.font) ? raw.font : DEFAULTS.font,
    };
  } catch {
    return DEFAULTS;
  }
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [{ theme, font }, setState] = useState(load);

  // <html data-theme data-font> 동기화 + 영속(localStorage; 후속 /api/ui-prefs).
  useEffect(() => {
    const el = document.documentElement;
    el.setAttribute("data-theme", theme);
    el.setAttribute("data-font", font);
    localStorage.setItem(KEY, JSON.stringify({ theme, font }));
  }, [theme, font]);

  const setTheme = useCallback((t: Theme) => setState((s) => ({ ...s, theme: t })), []);
  const setFont = useCallback((f: Font) => setState((s) => ({ ...s, font: f })), []);

  return (
    <ThemeContext.Provider value={{ theme, font, setTheme, setFont }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
