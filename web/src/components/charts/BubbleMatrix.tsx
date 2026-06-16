// 자동화 기회 버블 매트릭스 — X=난이도(쉬움→어려움), Y=효과/ROI(높음↑).
// 4분면 + 반경(score) + dept 색 + 충돌회피 오프셋 + 선택 글로우/halo + 클릭.
// (ui/board_v2·insights_v2 의 SVG 버블 승계)

export interface Bubble {
  key: string;
  label: string;
  dept: string;
  ease: number; // 0..1 (0=어려움, 1=쉬움)
  impact: number; // 0..1 (1=높음)
  score: number; // 반경 정규화용 (raw)
}

const DEPT_COLOR: Record<string, string> = {
  도장: "#2563EB", 용접: "#14B8A6", 의장: "#F59E0B", 조립: "#6366F1",
};
function deptColor(dept: string): string {
  for (const k of Object.keys(DEPT_COLOR)) if (dept.includes(k)) return DEPT_COLOR[k];
  return "#475569";
}

export default function BubbleMatrix({
  cells,
  selectedKey,
  onSelect,
  width = 600,
  height = 420,
}: {
  cells: Bubble[];
  selectedKey?: string | null;
  onSelect?: (key: string) => void;
  width?: number;
  height?: number;
}) {
  const padX = 40, padY = 20;
  const W = width - padX * 2, H = height - padY * 2;
  const maxScore = Math.max(1, ...cells.map((c) => c.score));

  // 위치 계산 + 충돌회피
  const placed: { key: string; cx: number; cy: number; r: number; b: Bubble }[] = [];
  for (const b of cells) {
    let cx = padX + b.ease * W;
    let cy = padY + (1 - b.impact) * H;
    const r = 14 + (b.score / maxScore) * 22;
    for (let guard = 0; guard < 12; guard++) {
      const hit = placed.find((p) => Math.hypot(p.cx - cx, p.cy - cy) < (p.r + r) * 0.55);
      if (!hit) break;
      cx -= 6; cy += 6; // 좌하로 단계 오프셋
    }
    placed.push({ key: b.key, cx, cy, r, b });
  }

  const quad = (x: number, y: number, w: number, h: number, label: string, hot = false) => (
    <g>
      <rect x={x} y={y} width={w} height={h} fill={hot ? "rgba(21,128,61,.06)" : "transparent"} />
      <text x={x + 8} y={y + 16} fontSize={11} fontWeight={hot ? 800 : 600}
        fill={hot ? "var(--semantic-success)" : "var(--text-muted)"}>{label}</text>
    </g>
  );

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="자동화 기회 매트릭스">
      {/* 4분면 */}
      {quad(padX, padY, W / 2, H / 2, "예측 R&D")}
      {quad(padX + W / 2, padY, W / 2, H / 2, "★ PoC 후보", true)}
      {quad(padX, padY + H / 2, W / 2, H / 2, "소규모 개선")}
      {quad(padX + W / 2, padY + H / 2, W / 2, H / 2, "유보 — 검토")}
      {/* 중앙 십자 */}
      <line x1={padX + W / 2} y1={padY} x2={padX + W / 2} y2={padY + H}
        stroke="var(--surface-divider)" strokeDasharray="3 3" />
      <line x1={padX} y1={padY + H / 2} x2={padX + W} y2={padY + H / 2}
        stroke="var(--surface-divider)" strokeDasharray="3 3" />
      {/* 축 라벨 */}
      <text x={padX} y={height - 4} fontSize={9} fill="var(--text-muted)">쉬움</text>
      <text x={padX + W} y={height - 4} fontSize={9} fill="var(--text-muted)" textAnchor="end">어려움</text>
      <text x={4} y={padY + 8} fontSize={9} fill="var(--text-muted)">높음</text>
      <text x={4} y={padY + H} fontSize={9} fill="var(--text-muted)">낮음</text>

      {/* 버블 */}
      {placed.map(({ key, cx, cy, r, b }) => {
        const color = deptColor(b.dept);
        const on = key === selectedKey;
        return (
          <g key={key} style={{ cursor: onSelect ? "pointer" : "default" }} onClick={() => onSelect?.(key)}>
            {on && <circle cx={cx} cy={cy} r={r + 8} fill="none" stroke={color}
              strokeDasharray="3 3" opacity={0.7} />}
            <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.16}
              stroke={color} strokeWidth={on ? 2.6 : 1.8} />
            <circle cx={cx} cy={cy} r={3} fill={color} />
            <text x={cx} y={cy - r - 3} fontSize={11} fontWeight={800} textAnchor="middle"
              fill={on ? "var(--accent-primary)" : "var(--text-primary)"}>
              {b.label.length > 12 ? b.label.slice(0, 12) + "…" : b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
