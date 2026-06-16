import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NAV_ALL } from "../nav";

// ⌘K 커맨드 팔레트 — 화면 빠른 이동 (ui/app_shell.py 승계).
export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const navigate = useNavigate();

  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    return NAV_ALL.filter((n) => !s || `${n.name} ${n.sub}`.toLowerCase().includes(s));
  }, [q]);

  useEffect(() => { setIdx(0); }, [q]);
  useEffect(() => { if (open) setQ(""); }, [open]);

  if (!open) return null;

  function go(to: string) {
    navigate(to);
    onClose();
  }

  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          className="cmdk-input"
          placeholder="화면 이동…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, items.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
            else if (e.key === "Enter" && items[idx]) go(items[idx].to);
            else if (e.key === "Escape") onClose();
          }}
        />
        <ul className="cmdk-list">
          {items.map((n, i) => (
            <li
              key={n.to}
              className={`cmdk-item${i === idx ? " on" : ""}`}
              onMouseEnter={() => setIdx(i)}
              onClick={() => go(n.to)}
            >
              <span className="cmdk-ic">{n.emoji}</span>
              <span><strong>{n.name}</strong> <span className="muted">{n.sub}</span></span>
            </li>
          ))}
          {items.length === 0 && <li className="cmdk-item muted">결과 없음</li>}
        </ul>
      </div>
    </div>
  );
}
