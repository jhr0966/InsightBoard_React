import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, streamChat } from "../api/client";
import type { ChatMessage } from "../api/types";

// 인계(?from=) → SOLA 자동 검토 prefill (ui/sola_workshop `_composer_prefill` 승계).
function handoffPrefill(from: string, dept: string, lv3: string): string {
  const target = [dept, lv3].filter(Boolean).join(" · ");
  if (from === "brief" || from === "board")
    return "오늘 보드 브리핑의 핵심 뉴스를 컨텍스트로, 부서장에게 보낼 1쪽 제안서 초안을 만들어줘.";
  if ((from === "matrix" || from === "opp") && target)
    return `${target} 자동화 기회에 대한 제안서 초안을 만들어줘.\n페르소나 컨텍스트로 ROI · 일정 · 위험요인을 포함해줘.`;
  if ((from === "insights" || from === "ia_map") && target)
    return `${target} 공정의 현재 상황과 매칭된 뉴스 신호를 정리하고, 적용 가능한 자동화 옵션 3가지를 비교해줘.`;
  if (target)
    return `${target} 작업에 적용할 자동화 기회를 외부 기술 동향과 연결해 검토해줘.`;
  return "";
}

// 화면별 추천질문 (클릭=즉시 전송) — ui/chat_panel 의 suggestion pills 승계.
const SUGGEST: Record<string, string[]> = {
  board: ["오늘 브리핑에서 우리 팀이 먼저 봐야 할 1건과 이유는?", "이번 주 가장 주목할 자동화 기회는?"],
  insights: ["왜 이 키워드가 뜨고 있나요?", "우리 조선소 어디에 적용 가능한가요?", "추천 PoC 과제 3가지는?"],
  collect: ["지금 화면 기사들 핵심만 3줄로 요약해줘", "이 중 우리 부서에 중요한 기사는?"],
  taskdefs: ["부서별 작업 정의에서 미등록 공정을 찾아줘", "이 작업의 자동화 포인트는?"],
  proposals: ["이 작업의 PoC 제안 초안을 만들어줘", "ROI·일정·위험요인을 정리해줘"],
  persona: ["내 관심사에 맞는 공정을 추천해줘"],
};

export default function AssistantDrawer({ screen, onClose }: { screen: string; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<string | null>(null);
  const [params] = useSearchParams();
  const firedRef = useRef<Set<string>>(new Set());

  async function persist(all: ChatMessage[]) {
    try {
      if (!threadRef.current) {
        const first = all.find((m) => m.role === "user")?.content ?? "";
        const t = await api.threads.create(first.slice(0, 36));
        threadRef.current = t.id;
      }
      const id = threadRef.current;
      if (id) await api.threads.saveMessages(id, all);
    } catch { /* 무시 */ }
  }

  async function send(textArg?: string) {
    const text = (textArg ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    let system: ChatMessage[] = [];
    try {
      const ctx = await api.assistant.context(screen);
      if (ctx.context) system = [{ role: "system", content: ctx.context }];
    } catch { /* 컨텍스트 없이 진행 */ }

    const history = [...messages, { role: "user", content: text } as ChatMessage];
    setMessages([...history, { role: "assistant", content: "" }]);

    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await streamChat([...system, ...history], (delta) => {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content: next[next.length - 1].content + delta };
          return next;
        });
      }, { signal: ac.signal });
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: `⚠️ ${(err as Error).message}` };
        return next;
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
      setMessages((prev) => { void persist(prev); return prev; });
    }
  }

  function reset() { setMessages([]); threadRef.current = null; }

  // 인계 도착 시 prefill 1회 자동 전송 (시그니처로 중복 방지 — 재마운트엔 sessionStorage).
  useEffect(() => {
    const from = params.get("from");
    if (!from) return;
    const dept = params.get("dept") ?? "";
    const lv3 = params.get("lv3") ?? "";
    const prefill = handoffPrefill(from, dept, lv3);
    if (!prefill) return;
    const sig = `${from}|${dept}|${lv3}`;
    const key = `sola.handoff.${sig}`;
    if (firedRef.current.has(sig) || sessionStorage.getItem(key)) return;
    firedRef.current.add(sig);
    sessionStorage.setItem(key, "1");
    void send(prefill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const pills = SUGGEST[screen] ?? [];

  return (
    <section className="drawer">
      <div className="drawer-header">
        <span>💬 SOLA</span>
        <span className="muted" style={{ fontSize: "var(--fs-micro)", marginLeft: 6 }}>· {screen}</span>
        <span style={{ float: "right", display: "flex", gap: 6 }}>
          <button className="oa-mini" onClick={reset} title="새 대화">＋</button>
          <button className="oa-mini" onClick={onClose}>닫기</button>
        </span>
      </div>
      <div className="drawer-log">
        {messages.length === 0 && (
          <div>
            <div className="muted" style={{ marginBottom: 10 }}>이 화면에 대해 무엇이든 물어보세요.</div>
            <div className="drawer-pills">
              {pills.map((p) => <button key={p} className="drawer-pill" disabled={busy} onClick={() => send(p)}>{p}</button>)}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content || (busy && i === messages.length - 1 ? "…" : "")}
          </div>
        ))}
      </div>
      <div className="drawer-input">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()} placeholder="메시지 입력…" disabled={busy} />
        <button className="btn primary" onClick={() => send()} disabled={busy || !input.trim()}>전송</button>
      </div>
    </section>
  );
}
