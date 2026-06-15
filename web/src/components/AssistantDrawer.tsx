import { useRef, useState } from "react";
import { api, streamChat } from "../api/client";
import type { ChatMessage } from "../api/types";

// 전역 어시스턴트 드로어 — SSE 스트리밍. 현재 화면 컨텍스트를 system 으로 주입.
export default function AssistantDrawer({
  screen,
  onClose,
}: {
  screen: string;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<string | null>(null);

  // 스레드 영구화 — 첫 메시지 때 스레드 생성, 교환 후 저장(best-effort).
  async function persist(all: ChatMessage[]) {
    try {
      if (!threadRef.current) {
        const first = all.find((m) => m.role === "user")?.content ?? "";
        const t = await api.threads.create(first.slice(0, 36));
        threadRef.current = t.id;
      }
      const id = threadRef.current;
      if (id) await api.threads.saveMessages(id, all);
    } catch {
      /* 영구화 실패는 무시(대화는 계속) */
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    // 화면 컨텍스트를 system 으로 (실패해도 챗은 진행).
    let system: ChatMessage[] = [];
    try {
      const ctx = await api.assistant.context(screen);
      if (ctx.context) system = [{ role: "system", content: ctx.context }];
    } catch {
      /* 컨텍스트 없이 진행 */
    }

    const userMsg: ChatMessage = { role: "user", content: text };
    const history = [...messages, userMsg];
    setMessages([...history, { role: "assistant", content: "" }]);

    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await streamChat([...system, ...history], (delta) => {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: next[next.length - 1].content + delta,
          };
          return next;
        });
      }, { signal: ac.signal });
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `⚠️ ${(err as Error).message}`,
        };
        return next;
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
      setMessages((prev) => {
        void persist(prev);
        return prev;
      });
    }
  }

  return (
    <section className="drawer">
      <div className="drawer-header">
        💬 SOLA 어시스턴트 <span className="muted">· {screen}</span>
        <button className="btn" style={{ float: "right" }} onClick={onClose}>
          닫기
        </button>
      </div>
      <div className="drawer-log">
        {messages.length === 0 && <div className="muted">현재 화면에 대해 질문해 보세요.</div>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content || (busy && i === messages.length - 1 ? "…" : "")}
          </div>
        ))}
      </div>
      <div className="drawer-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="메시지 입력…"
          disabled={busy}
        />
        <button className="btn primary" onClick={send} disabled={busy || !input.trim()}>
          전송
        </button>
      </div>
    </section>
  );
}
