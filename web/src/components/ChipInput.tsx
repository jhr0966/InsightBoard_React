import { useState } from "react";

// 칩 입력 — Enter 로 추가, × 로 제거 (관심공정/키워드).
export default function ChipInput({
  values, onChange, placeholder,
}: { values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [text, setText] = useState("");
  function add() {
    const t = text.trim();
    if (t && !values.includes(t)) onChange([...values, t]);
    setText("");
  }
  return (
    <div className="chip-input">
      {values.map((v) => (
        <span className="chip-input-chip" key={v}>
          {v}<button onClick={() => onChange(values.filter((x) => x !== v))} aria-label="remove">×</button>
        </span>
      ))}
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        onBlur={add}
        placeholder={placeholder}
      />
    </div>
  );
}
