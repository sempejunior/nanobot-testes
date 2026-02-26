import { useState, useRef, useEffect, useCallback } from "react";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Send, Loader2 } from "lucide-react";

export function ChatInput() {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, sending, connected } = useStore();
  const wasSendingRef = useRef(false);

  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 240) + "px";
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [text, adjustHeight]);

  // Re-focus textarea ONLY after a send completes (sending: true → false)
  useEffect(() => {
    if (wasSendingRef.current && !sending) {
      textareaRef.current?.focus();
    }
    wasSendingRef.current = sending;
  }, [sending]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || sending || !connected) return;
    sendMessage(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-white/[0.06] bg-white/[0.02] backdrop-blur-md px-4 py-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-end gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-3 focus-within:border-green/40 focus-within:ring-2 focus-within:ring-green/15 focus-within:shadow-[0_0_20px_rgba(17,199,111,0.1)] transition-all duration-200">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={connected ? "Send a message..." : "Reconnecting..."}
            disabled={sending}
            rows={2}
            className="flex-1 bg-transparent text-text-primary placeholder:text-text-muted text-[15px] leading-relaxed resize-none focus:outline-none px-2 py-2 max-h-[240px]"
          />
          <Button
            size="icon"
            onClick={handleSubmit}
            disabled={!text.trim() || sending || !connected}
            className="shrink-0 w-10 h-10"
          >
            {sending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>
        <p className="text-xs text-text-muted text-center mt-2 opacity-60">
          nanobot can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  );
}
