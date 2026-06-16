// 상대시간 라벨 — 방금 / N분 전 / N시간 전 / 어제 / M월 D일 (ui 의 _news_age_label 승계).
export function ageLabel(when?: string | null): string {
  if (!when) return "";
  const t = Date.parse(when.replace(" ", "T"));
  if (Number.isNaN(t)) return "";
  const diffMs = Date.now() - t;
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  const day = Math.floor(hr / 24);
  if (day === 1) return "어제";
  if (day < 7) return `${day}일 전`;
  const d = new Date(t);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}
