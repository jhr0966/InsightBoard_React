import { useEffect, useRef, type ReactNode, type KeyboardEvent as ReactKeyboardEvent } from "react";

// ── 공통 UI 컴포넌트 (assets/v2 디자인 토큰 기반) ──

// 클릭 가능한 div/tr 을 키보드로도 조작 가능하게 — role="button"+tabIndex+Enter/Space.
// 마우스 onClick 만 있던 요소에 스프레드해서 접근성 표준화. label 은 aria-label(선택).
export function clickableProps(onClick: () => void, label?: string) {
  return {
    role: "button",
    tabIndex: 0,
    ...(label ? { "aria-label": label } : {}),
    onClick,
    onKeyDown: (e: ReactKeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onClick();
      }
    },
  };
}

export function Card({ title, children, className = "" }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`card ${className}`}>
      {title && <div className="card-title">{title}</div>}
      {children}
    </div>
  );
}

export type Tone = "default" | "accent" | "success" | "warning" | "danger" | "info";

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Chip({ children, dot }: { children: ReactNode; dot?: string }) {
  return (
    <span className="chip">
      {dot && <span className="chip-dot" style={{ background: dot }} />}
      {children}
    </span>
  );
}

// 델타 배지 (↑/↓/· %) — KPI 카드용
export function Delta({ value }: { value?: number | null }) {
  if (value == null) return null;
  const tone: Tone = value > 0 ? "success" : value < 0 ? "danger" : "default";
  const arrow = value > 0 ? "↑" : value < 0 ? "↓" : "·";
  return <Badge tone={tone}>{arrow} {Math.abs(value)}%</Badge>;
}

export interface KPI {
  label: string;
  value: ReactNode;
  delta?: number | null;
  tone?: Tone;
}

export function KPIStatGrid({ items, cols = 4 }: { items: KPI[]; cols?: number }) {
  return (
    <div className="kpi-grid" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {items.map((k) => (
        <div className="kpi-card" key={k.label}>
          <div className="kpi-label">{k.label}</div>
          <div className="kpi-value-row">
            <span className={`kpi-value${k.tone ? ` t-${k.tone}` : ""}`}>{k.value}</span>
            <Delta value={k.delta} />
          </div>
        </div>
      ))}
    </div>
  );
}

export interface TabItem { key: string; label: ReactNode; }

export function Tabs({ items, value, onChange }: { items: TabItem[]; value: string; onChange: (k: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === value}
          className={`tab${t.key === value ? " on" : ""}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({ icon = "🗂", title, hint }: { icon?: string; title: string; hint?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state-ic">{icon}</div>
      <div className="empty-state-title">{title}</div>
      {hint && <div className="muted">{hint}</div>}
    </div>
  );
}

// 조회 실패 상태 — 빈 상태("데이터 없음")와 명확히 구분한다. 무료 호스팅 슬립/재배포로
// 백엔드가 잠깐 죽는 경로가 잦아, "기사가 없어요" 대신 진짜 원인(연결 실패)을 보여준다.
export function LoadError({
  message = "불러오지 못했어요",
  hint = "잠시 후 다시 시도해 주세요. 백엔드가 깨어나는 중일 수 있어요.",
  onRetry,
  compact = false,
}: { message?: string; hint?: ReactNode; onRetry?: () => void; compact?: boolean }) {
  if (compact) {
    return (
      <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--fs-caption)" }}>
        <span style={{ color: "var(--semantic-danger)" }}>⚠ {message}</span>
        {onRetry && <button className="btn" style={{ padding: "2px 10px" }} onClick={onRetry}>다시 시도</button>}
      </div>
    );
  }
  return (
    <div className="empty-state">
      <div className="empty-state-ic">⚠️</div>
      <div className="empty-state-title">{message}</div>
      <div className="muted">{hint}</div>
      {onRetry && <button className="btn" style={{ marginTop: 10 }} onClick={onRetry}>다시 시도</button>}
    </div>
  );
}

// 모달/다이얼로그 — dismissible 제어(false 면 backdrop/Esc 로 안 닫힘)
export function Modal({
  open,
  onClose,
  title,
  children,
  dismissible = true,
  width = 560,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  dismissible?: boolean;
  width?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // Esc 로 닫기(dismissible 일 때만) + 열릴 때 모달로 포커스 이동(키보드 사용자·스크린리더).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && dismissible) onClose(); };
    document.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, dismissible, onClose]);
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={() => dismissible && onClose()}>
      <div className="modal" ref={ref} tabIndex={-1} role="dialog" aria-modal="true"
        style={{ width: `min(${width}px, 94vw)` }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>{title}</span>
          {/* dismissible=false(온보딩 등)면 ✕ 를 숨겨 '닫기 금지' 의도를 지킨다. */}
          {dismissible && <button className="btn" aria-label="닫기" onClick={onClose}>✕</button>}
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
