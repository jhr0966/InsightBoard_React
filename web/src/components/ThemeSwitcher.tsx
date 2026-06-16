import { FONTS, THEMES, useTheme } from "../theme/ThemeProvider";

const THEME_LABEL: Record<string, string> = {
  light: "라이트", dark: "다크", ocean: "오션", sunset: "선셋",
};
const FONT_LABEL: Record<string, string> = {
  small: "작게", medium: "보통", large: "크게",
};

// 표시 설정 — 페르소나 페이지의 "🎨 표시 설정" 승계(어디서나 재사용).
export default function ThemeSwitcher() {
  const { theme, font, setTheme, setFont } = useTheme();
  return (
    <div className="theme-switcher">
      <div className="theme-row">
        <span className="muted">테마</span>
        <div className="seg">
          {THEMES.map((t) => (
            <button
              key={t}
              className={`seg-btn${t === theme ? " on" : ""}`}
              onClick={() => setTheme(t)}
            >
              {THEME_LABEL[t]}
            </button>
          ))}
        </div>
      </div>
      <div className="theme-row">
        <span className="muted">글자</span>
        <div className="seg">
          {FONTS.map((f) => (
            <button
              key={f}
              className={`seg-btn${f === font ? " on" : ""}`}
              onClick={() => setFont(f)}
            >
              {FONT_LABEL[f]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
