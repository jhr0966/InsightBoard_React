import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Modal } from "./ui";
import ChipInput from "./ChipInput";
import type { Persona } from "../api/types";

const DISMISS = "onb.dismissed";

// 온보딩 마법사 — 페르소나 미설정 시 노출. 6단계.
export default function Onboarding({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [d, setD] = useState({ name: "", team: "", dept: "", job: "", interest_lv3: [] as string[], interest_keywords: [] as string[] });
  const set = (patch: Partial<typeof d>) => setD({ ...d, ...patch });

  const save = useMutation({
    mutationFn: () => api.persona.save(d as Partial<Persona>),
    // 저장·derive 후 닫지 않고 '첫 수집' 제안 단계(5)로.
    onSuccess: (p) => { qc.setQueryData(["persona"], p); api.persona.derive().catch(() => {}); setStep(5); },
  });
  // 설정 후 첫 수집 — 관심 키워드 기준(비면 도메인 기본). Streamlit 온보딩 step5/6 이식.
  const collect = useMutation({
    mutationFn: () => api.collect.run(d.interest_keywords, { do_enrich: true }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["news"] }); qc.invalidateQueries({ queryKey: ["collect"] }); finish(); },
    onError: () => finish(),  // 수집 실패해도 온보딩은 완료
  });

  function dismiss() { localStorage.setItem(DISMISS, "1"); onClose(); }
  function finish() { localStorage.setItem(DISMISS, "1"); qc.invalidateQueries({ queryKey: ["persona"] }); onClose(); }

  const STEPS = 5; // 0 환영, 1 이름, 2 팀·부서, 3 직무, 4 관심사, (5 첫 수집 제안)

  return (
    <Modal open onClose={dismiss} dismissible={false} width={480}
      title={step === 0 ? "반갑습니다 👋" : step >= 5 ? "준비 완료 🎉" : `설정 ${step} / 4`}>
      {step > 0 && step < STEPS && (
        <div className="onb-steps">
          {[1, 2, 3, 4].map((s) => <span key={s} className={`onb-dot${s === step ? " on" : s < step ? " done" : ""}`} />)}
        </div>
      )}

      {step === 0 && (
        <div className="onb-hero">
          <div className="onb-emoji">🚀</div>
          <div className="onb-title">맞춤 인사이트, 1분이면 준비 완료</div>
          <div className="onb-sub">부서·직무·관심 공정을 알려주시면 <b>오늘의 보드</b>와 <b>SOLA</b>가 당신의 작업에 맞춰 채워집니다.</div>
        </div>
      )}
      {step === 1 && <Field label="이름을 알려주세요" value={d.name} onChange={(v) => set({ name: v })} />}
      {step === 2 && <>
        <Field label="팀" value={d.team} onChange={(v) => set({ team: v })} />
        <Field label="부서" value={d.dept} onChange={(v) => set({ dept: v })} />
      </>}
      {step === 3 && <Field label="직무 (예: 용접 담당)" value={d.job} onChange={(v) => set({ job: v })} />}
      {step === 4 && <>
        <div className="onb-field"><label>관심 공정</label>
          <ChipInput values={d.interest_lv3} onChange={(v) => set({ interest_lv3: v })} placeholder="입력 후 Enter" /></div>
        <div className="onb-field"><label>관심 키워드</label>
          <ChipInput values={d.interest_keywords} onChange={(v) => set({ interest_keywords: v })} placeholder="예: 용접 로봇" /></div>
      </>}
      {step === 5 && (
        <div className="onb-hero">
          <div className="onb-emoji">✅</div>
          <div className="onb-title">설정이 끝났어요!</div>
          <div className="onb-sub">바로 <b>첫 뉴스를 수집</b>해 보드를 채울까요? 관심 키워드 기준으로 모읍니다(최대 1분).</div>
        </div>
      )}

      <div className="onb-nav">
        {step === 0 ? <>
          <button className="btn" onClick={dismiss}>나중에 하기</button>
          <button className="btn primary" style={{ marginLeft: "auto" }} onClick={() => setStep(1)}>설정 시작하기</button>
        </> : step === 5 ? <>
          <button className="btn" onClick={finish} disabled={collect.isPending}>건너뛰기</button>
          <button className="btn primary" style={{ marginLeft: "auto" }} disabled={collect.isPending} onClick={() => collect.mutate()}>
            {collect.isPending ? "수집 중… (최대 1분)" : "📡 지금 첫 수집"}</button>
        </> : <>
          <button className="btn" onClick={() => setStep(step - 1)}>← 이전</button>
          {step < 4
            ? <button className="btn primary" style={{ marginLeft: "auto" }} onClick={() => setStep(step + 1)}>다음 →</button>
            : <button className="btn primary" style={{ marginLeft: "auto" }} disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? "저장 중…" : "✓ 완료"}</button>}
        </>}
      </div>
    </Modal>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="onb-field">
      <label>{label}</label>
      <input autoFocus value={value} onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
    </div>
  );
}

export function shouldOnboard(personaIsSet: boolean | undefined): boolean {
  return personaIsSet === false && localStorage.getItem(DISMISS) !== "1";
}
