import type { ReactNode } from "react";

// ── 공통 UI 컴포넌트 (assets/v2 디자인 토큰 기반) ──

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
  if (!open) return null;
  return (
    <div className="modal-overlay" onClick={() => dismissible && onClose()}>
      <div className="modal" style={{ width: `min(${width}px, 94vw)` }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>{title}</span>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
