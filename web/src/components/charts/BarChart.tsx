// 막대차트 — 수집량(14일). 마지막(오늘) 강조, 호버 title.
export interface Bar { label: string; value: number; title?: string; highlight?: boolean; }

export default function BarChart({
  bars,
  width = 320,
  height = 80,
}: {
  bars: Bar[];
  width?: number;
  height?: number;
}) {
  const padB = 4;
  const H = height - padB;
  const max = Math.max(1, ...bars.map((b) => b.value));
  const n = bars.length || 1;
  const gap = 3;
  const bw = Math.max(2, (width - gap * (n - 1)) / n);
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="수집량 막대차트">
      <line x1={0} x2={width} y1={H} y2={H} stroke="var(--surface-divider)" strokeWidth={1} />
      {bars.map((b, i) => {
        const h = (b.value / max) * (H - 2);
        const x = i * (bw + gap);
        return (
          <rect key={i} x={x} y={H - h} width={bw} height={h} rx={1.5}
            fill={b.highlight ? "var(--accent-primary)" : "var(--surface-divider)"}>
            <title>{b.title ?? `${b.label}: ${b.value}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}
