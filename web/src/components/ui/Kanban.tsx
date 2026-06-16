import type { ReactNode } from "react";

// 칸반 — 보관함(대기/채택/기각) 3열 (ui/archive_v2.py 승계).
export function KanbanBoard({ children }: { children: ReactNode }) {
  return <div className="kanban">{children}</div>;
}

export function KanbanColumn({
  title,
  count,
  dot,
  desc,
  actions,
  children,
}: {
  title: string;
  count: number;
  dot: string;
  desc?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="kanban-col">
      <div className="kanban-col-head">
        <span className="kanban-dot" style={{ background: dot }} />
        <strong>{title}</strong>
        <span className="kanban-count">{count}</span>
      </div>
      {desc && <div className="muted kanban-col-desc">{desc}</div>}
      {actions && <div className="kanban-col-actions">{actions}</div>}
      <div className="kanban-cards">{children}</div>
    </div>
  );
}
