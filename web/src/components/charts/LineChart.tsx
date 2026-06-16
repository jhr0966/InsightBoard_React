// 다계열 라인차트 — 트렌드(8주/일간). top 계열 강조 + 마커 + 격자 + 범례.
// 적응형 granularity(주간↔일간)는 호출부가 labels/series 를 그 단위로 넘겨 결정.
const SERIES_COLORS = [
  "var(--chart-series-1)", "var(--chart-series-2)", "var(--chart-series-3)",
  "var(--chart-series-4)", "var(--chart-series-5)", "var(--chart-series-6)",
];

export interface Series { name: string; values: number[]; }

export default function LineChart({
  series,
  labels,
  width = 540,
  height = 220,
  highlightTop = 3,
}: {
  series: Series[];
  labels: string[];
  width?: number;
  height?: number;
  highlightTop?: number;
}) {
  const padL = 8, padR = 8, padT = 14, padB = 22;
  const W = width - padL - padR, H = height - padT - padB;
  const n = labels.length;
  const allMax = Math.max(1, ...series.flatMap((s) => s.values));
  const yMax = niceMax(allMax);
  const x = (i: number) => padL + (n <= 1 ? W / 2 : (i / (n - 1)) * W);
  const y = (v: number) => padT + H - (v / yMax) * H;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="트렌드 라인차트">
      {/* 격자 + y 눈금 */}
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={padL} x2={width - padR} y1={padT + H - t * H} y2={padT + H - t * H}
            stroke="var(--surface-divider)" strokeWidth={1} opacity={0.6} />
          <text x={padL} y={padT + H - t * H - 2} fontSize={9} fill="var(--text-muted)">
            {Math.round(yMax * t)}
          </text>
        </g>
      ))}
      {/* x 라벨 */}
      {labels.map((l, i) => (
        <text key={i} x={x(i)} y={height - 6} fontSize={9} fill="var(--text-muted)"
          textAnchor="middle">{l}</text>
      ))}
      {/* 계열 */}
      {series.map((s, si) => {
        const color = SERIES_COLORS[si % SERIES_COLORS.length];
        const hot = si < highlightTop;
        const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
        return (
          <g key={s.name} opacity={hot ? 1 : 0.45}>
            <polyline points={pts} fill="none" stroke={color}
              strokeWidth={hot ? 2.2 : 1.4} strokeLinejoin="round" strokeLinecap="round" />
            {si === 0 && s.values.length > 0 && (
              <circle cx={x(s.values.length - 1)} cy={y(s.values[s.values.length - 1])} r={3.5}
                fill={color} />
            )}
          </g>
        );
      })}
    </svg>
  );
}

function niceMax(v: number): number {
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const norm = v / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return Math.max(1, nice * mag * 1.25);
}
