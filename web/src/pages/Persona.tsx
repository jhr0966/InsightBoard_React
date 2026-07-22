import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ChipInput from "../components/ChipInput";
import ThemeSwitcher from "../components/ThemeSwitcher";
import { Chip, LoadError } from "../components/ui";
import { useToast } from "../components/ui/toast";
import type { Persona } from "../api/types";

export default function PersonaPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const loaded = useQuery({ queryKey: ["persona"], queryFn: () => api.persona.get() });
  const [p, setP] = useState<Persona | null>(null);
  useEffect(() => { if (loaded.data && !p) setP(loaded.data); }, [loaded.data, p]);

  const save = useMutation({
    mutationFn: (body: Persona) => api.persona.save(body),
    onSuccess: (d) => { qc.setQueryData(["persona"], d); setP(d); toast.push("✅ 페르소나를 저장했어요", "success"); },
    onError: (e) => toast.push(`저장 실패: ${(e as Error).message}`, "danger"),
  });
  const derive = useMutation({
    // 분석 전 현재 폼 입력을 먼저 저장 — 저장 안 한 입력이 날아가고 옛 데이터로
    // 분석되던 버그 방지. 서버 derive 는 저장된 페르소나를 읽으므로 save 가 선행해야 함.
    mutationFn: async () => {
      if (p) await api.persona.save(p);
      return api.persona.derive();
    },
    onSuccess: (d) => { qc.setQueryData(["persona"], d); setP(d); toast.push("🤖 SOLA 분석 완료", "success"); },
    onError: (e) => toast.push(`분석 실패: ${(e as Error).message}`, "danger"),
  });
  const reset = useMutation({
    mutationFn: () => api.persona.reset(),
    onSuccess: (d) => { qc.setQueryData(["persona"], d); setP(d); toast.push("초기화됨", "default"); },
    onError: (e) => toast.push(`초기화 실패: ${(e as Error).message}`, "danger"),
  });

  // 로드 실패 시 영구 스피너에 갇히지 않게 — 오류+재시도를 명확히 보여준다.
  if (loaded.isError && !p)
    return <LoadError message="페르소나를 불러오지 못했어요" onRetry={() => loaded.refetch()} />;
  if (!p) return <div className="muted">불러오는 중…</div>;
  const set = (patch: Partial<Persona>) => setP({ ...p, ...patch });

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: "var(--fs-headline-lg)", fontWeight: "var(--fw-black)" }}>페르소나 설정</div>
          <div className="muted" style={{ fontSize: "var(--fs-caption)" }}>부서·직무·관심사를 설정하면 보드·인사이트·SOLA가 개인화됩니다.</div>
        </div>
        <button className="btn" style={{ marginLeft: "auto" }} onClick={() => nav("/")}>← 돌아가기</button>
      </div>

      <div className="card">
        <div className="card-title">① 기본 정보</div>
        <div className="pf-grid">
          <div className="pf-field"><label>이름</label><input value={p.name} onChange={(e) => set({ name: e.target.value })} /></div>
          <div className="pf-field"><label>팀</label><input value={p.team} onChange={(e) => set({ team: e.target.value })} /></div>
          <div className="pf-field"><label>부서</label><input value={p.dept} onChange={(e) => set({ dept: e.target.value })} /></div>
          <div className="pf-field"><label>직무</label><input value={p.job} onChange={(e) => set({ job: e.target.value })} /></div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">② 관심사</div>
        <div className="pf-field" style={{ marginBottom: 12 }}>
          <label>관심 공정</label>
          <ChipInput values={p.interest_lv3 ?? []} onChange={(v) => set({ interest_lv3: v })} placeholder="예: 전처리 — 입력 후 Enter" />
        </div>
        <div className="pf-field">
          <label>관심 키워드</label>
          <ChipInput values={p.interest_keywords ?? []} onChange={(v) => set({ interest_keywords: v })} placeholder="예: 용접 로봇 — 입력 후 Enter" />
        </div>
      </div>

      <div className="card">
        <div className="card-title">③ SOLA가 분석한 내 관심 공정/작업</div>
        {(p.derived_interests ?? []).length > 0 ? <>
          <div className="muted" style={{ fontSize: "var(--fs-micro)" }}>
            🤖 {p.derived_source === "fallback" ? "규칙 기반" : "SOLA(LLM)"} 분석 {p.derived_at && `· ${p.derived_at.slice(0, 10)}`}</div>
          <div className="pf-derived">{(p.derived_interests ?? []).map((k) => <Chip key={k}>{k}</Chip>)}</div>
          {(p.matched_processes ?? []).slice(0, 8).map((m: any, i) => (
            <div className="pf-proc" key={i}><b>{m.process || m.lv3 || "(공정)"}</b> {m.tasks ? `· ${(m.tasks as string[]).slice(0, 5).join(", ")}` : ""}</div>
          ))}
        </> : <div className="muted">아직 분석 결과가 없어요. 저장하거나 아래 ‘지금 분석’을 누르세요.</div>}
        <button className="btn" style={{ marginTop: 12 }} disabled={derive.isPending} onClick={() => derive.mutate()}>
          {derive.isPending ? "분석 중…" : (p.derived_interests ?? []).length > 0 ? "🔄 다시 분석" : "✨ 지금 분석"}</button>
      </div>

      <div className="card">
        <div className="card-title">🎨 표시 설정</div>
        <ThemeSwitcher />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn primary" disabled={save.isPending} onClick={() => save.mutate(p)}>{save.isPending ? "저장 중…" : "💾 저장"}</button>
        <button className="btn" onClick={() => confirm("페르소나를 초기화할까요?") && reset.mutate()}>초기화</button>
      </div>
    </div>
  );
}
