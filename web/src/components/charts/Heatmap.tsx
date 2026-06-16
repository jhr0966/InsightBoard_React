// 공정×기술 히트맵 — 색강도 5단계 + 셀 선택 (ui/insights_v2 승계).
export interface HeatCell { value: number; }

const LEVELS = [
  { max: 0, bg: "transparent", border: "dashed" },
  { max: 3, bg: "rgba(37,99,235,.12)", border: "solid" },
  { max: 7, bg: "rgba(37,99,235,.28)", border: "solid" },
  { max: 15, bg: "rgba(37,99,235,.48)", border: "solid" },
  { max: Infinity, bg: "rgba(37,99,235,.72)", border: "solid" },
];
function level(v: number) {
  return LEVELS.find((l) => v <= l.max) ?? LEVELS[LEVELS.length - 1];
}

export default function Heatmap({
  rows,
  cols,
  data,
  selected,
  onSelect,
}: {
  rows: string[];
  cols: string[];
  data: number[][]; // data[r][c]
  selected?: string | null; // "row||col"
  onSelect?: (key: string) => void;
}) {
  return (
    <div className="heatmap">
      <table className="heatmap-tbl">
        <thead>
          <tr>
            <th />
            {cols.map((c) => <th key={c} className="heatmap-col">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={r}>
              <td className="heatmap-row">{r}</td>
              {cols.map((c, ci) => {
                const v = data[ri]?.[ci] ?? 0;
                const lv = level(v);
                const key = `${r}||${c}`;
                const on = key === selected;
                return (
                  <td key={c} className="heatmap-cell">
                    <button
                      className={`heatmap-c${on ? " on" : ""}`}
                      style={{ background: lv.bg, borderStyle: lv.border,
                        color: v > 7 ? "#fff" : "var(--text-secondary)" }}
                      onClick={() => onSelect?.(key)}
                      title={`${r} × ${c}: ${v}건`}
                    >
                      {v || ""}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
