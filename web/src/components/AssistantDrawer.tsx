import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, streamChat } from "../api/client";
import type { ChatMessage } from "../api/types";

// 인계(?from=) → SOLA 자동 검토 prefill (ui/sola_workshop `_composer_prefill` 승계).
function handoffPrefill(from: string, dept: string, lv3: string, work = ""): string {
  const target = [dept, lv3].filter(Boolean).join(" · ");
  if (from === "case")
    return `방금 넘어온 적용 사례${work ? `(${work})` : ""}를 우리 조선소 작업에 적용하는 제안서 초안을 검토해줘.\n사례의 정량 효과를 근거로, 우리 상황에 맞는 PoC 범위·기대 효과·위험요인을 정리해줘.`;
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

// 화면별 안내 헤드라인 + 추천질문 (클릭=즉시 전송) — ui/chat_panel `_AREA_INTROS` 승계.
// 추천 질문 = "이 화면에서 SOLA 를 이렇게 쓰는 겁니다" 시연 — 화면 데이터를 실제로
// 읽어야 답할 수 있는 구체적 행동(요약·비교·보고서 초안·다음 단계)으로 구성.
interface Intro { headline: string; suggestions: string[]; }
const INTROS: Record<string, Intro> = {
  board: {
    headline: "📊 오늘의 보드 — SOLA 가 이 화면 데이터를 알고 있어요",
    suggestions: [
      "오늘 브리핑 5건 중 우리 팀이 가장 먼저 봐야 할 1건과 그 이유는?",
      "자동화 제안 1위를 PoC 로 시작한다면 다음 주 할 일 3가지 뽑아줘",
      "트렌드에서 '신규' 표시된 키워드만 골라 왜 떴는지 설명해줘",
      "오늘 화면 내용으로 팀장 보고용 3줄 요약 써줘",
      "매트릭스 우상단 후보의 기대 효과와 리스크를 표로 비교해줘",
    ],
  },
  insights: {
    headline: "🔎 인사이트 분석 — 트렌드·매트릭스·공정 매핑을 알고 있어요",
    suggestions: [
      "트렌드 top 키워드의 추이를 해석하고 우리 작업과 연결해줘",
      "신규 등장 키워드가 어떤 공정에 영향을 줄지 짚어줘",
      "매트릭스 top 3 후보를 효과·난이도·근거 뉴스로 비교해줘",
      "히트맵에서 가장 뜨거운 공정×기술 조합의 다음 단계는?",
      "이 화면 내용으로 월간 기술 동향 보고 초안 써줘",
    ],
  },
  proposals: {
    headline: "🤖 자동화 제안 — 작업·매칭 뉴스·이전 대화를 컨텍스트로 써요",
    suggestions: [
      "지금 작업 중인 산출물의 약한 부분을 지적하고 보강안 줘",
      "이 작업의 PoC 제안 초안을 ROI·일정·위험요인까지 정리해줘",
      "이 제안서를 임원 보고용 1장으로 압축해줘",
      "이전 thread 에서 결정된 사항만 모아 정리해줘",
    ],
  },
  feed: {
    headline: "🗞 뉴스 탐색 — 지금 보이는 기사들을 알고 있어요",
    suggestions: [
      "지금 화면에 보이는 기사들 핵심만 3줄로 요약해줘",
      "오늘 수집분에서 우리 부서가 참고할 기사 3건 골라 이유와 함께",
      "이 중 자동화 과제로 발전시킬 만한 기사를 골라 이유를 설명해줘",
      "이번 주 수집 기사로 주간 기술 동향 리포트 초안 써줘",
    ],
  },
  cases: {
    headline: "📚 적용 사례 — 정제된 사례들을 알고 있어요",
    suggestions: [
      "검토 대기 사례 중 우리 조선소에 가장 잘 맞는 것 3건과 이유는?",
      "승인된 사례들을 기술별로 묶어 한 줄씩 정리해줘",
      "이 사례를 우리 공정에 접목할 때 첫 단계는 뭘까?",
    ],
  },
  collect: {
    headline: "⚙️ 수집 관리 — 수집 상태·출처 헬스를 알고 있어요",
    suggestions: [
      "출처별 7일 수집량을 보고 수집이 줄어든 출처와 원인 추정해줘",
      "지금 키워드에 추가하면 좋을 검색어 3개를 근거와 함께 추천해줘",
      "본문 확보율이 낮다면 원인 후보를 짚어줘",
    ],
  },
  taskdefs: {
    headline: "📋 작업 정의 — 등록된 작업 정의·부서 분포를 알고 있어요",
    suggestions: [
      "부서별 작업 정의 분포에서 빈 곳(미등록 공정)을 찾아줘",
      "등록된 작업 중 자동화 효과가 클 것 같은 3건과 이유는?",
      "최근 추가된 작업 정의를 한 줄씩 요약해줘",
      "작업 정의를 더 채우려면 어떤 항목부터 보강해야 할까?",
      "엑셀 업로드 형식(필수 컬럼)을 알려줘",
    ],
  },
  persona: {
    headline: "👤 페르소나 설정 — 더 좋은 컨텍스트 설정을 도와드려요",
    suggestions: [
      "내 부서·직무 기준으로 관심 공정을 추천해줘",
      "지금 설정에서 비어 있는 항목과 채우면 좋아지는 점은?",
      "뉴스가 더 잘 잡히도록 관심 키워드 5개 제안해줘",
    ],
  },
};

export default function AssistantDrawer({ screen, onClose }: { screen: string; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [ctxLabels, setCtxLabels] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<string | null>(null);
  const [params] = useSearchParams();
  const firedRef = useRef<Set<string>>(new Set());

  async function persist(all: ChatMessage[]) {
    try {
      if (!threadRef.current) {
        const first = all.find((m) => m.role === "user")?.content ?? "";
        // 첫 메시지를 서버로 보내 LLM 제목 자동 생성(미설정 시 룰 fallback).
        const t = await api.threads.create({ first_message: first });
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
      // 입력 텍스트를 query 로 넘겨 — 언급한 작업의 작업정의가 컨텍스트에 주입된다.
      const ctx = await api.assistant.context(screen, text);
      if (ctx.context) system = [{ role: "system", content: ctx.context }];
      setCtxLabels(ctx.labels ?? []);
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
    const work = params.get("work") ?? "";
    const prefill = handoffPrefill(from, dept, lv3, work);
    if (!prefill) return;
    const sig = `${from}|${dept}|${lv3}|${work}`;
    const key = `sola.handoff.${sig}`;
    if (firedRef.current.has(sig) || sessionStorage.getItem(key)) return;
    firedRef.current.add(sig);
    sessionStorage.setItem(key, "1");
    void send(prefill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const intro = INTROS[screen] ?? INTROS.board;

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
        {/* 안내 헤드라인 + 추천 질문 — 대화가 쌓여도 상단에 남아 함께 스크롤(ui/chat_panel 승계). */}
        <div className="drawer-intro">
          <div className="drawer-intro-h">{intro.headline}</div>
          <div className="drawer-intro-sub">아래 입력창에 직접 적거나, 추천 질문을 누르면 바로 전송됩니다.</div>
        </div>
        <div className="drawer-pills">
          {intro.suggestions.map((p) => (
            <button key={p} className="drawer-pill" disabled={busy} onClick={() => send(p)}>{p}</button>
          ))}
        </div>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content || (busy && i === messages.length - 1 ? "…" : "")}
          </div>
        ))}
      </div>
      {ctxLabels.length > 0 && (
        <div className="drawer-ctx" title="이번 답변에 주입된 컨텍스트">
          📎 {ctxLabels.join(" · ")}
        </div>
      )}
      <div className="drawer-input">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()} placeholder="메시지 입력…" disabled={busy} />
        <button className="btn primary" onClick={() => send()} disabled={busy || !input.trim()}>전송</button>
      </div>
    </section>
  );
}
