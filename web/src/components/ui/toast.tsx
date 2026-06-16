import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import type { Tone } from "./index";

// 1회성 토스트 — 액션(채택/저장/수집 등) 후 알림 (ui 의 *_toast 승계).
interface Toast { id: number; text: string; tone: Tone; }
interface ToastCtx { push: (text: string, tone?: Tone) => void; }

const Ctx = createContext<ToastCtx | null>(null);
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, tone: Tone = "default") => {
    const id = ++seq;
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="toast-host">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useToast must be used within ToastProvider");
  return c;
}
