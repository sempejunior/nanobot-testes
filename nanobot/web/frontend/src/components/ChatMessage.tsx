import { useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Wrench, Loader2, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Code block with copy button ──────────────────────────────────────

function CodeBlock(props: React.ComponentPropsWithoutRef<"pre"> & { node?: unknown }) {
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLPreElement>(null);

  const handleCopy = useCallback(() => {
    const text = ref.current?.textContent || "";
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, []);

  return (
    <div className="relative group/code">
      <pre ref={ref} className={props.className}>
        {props.children}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-md bg-white/[0.06] border border-white/[0.08] text-text-muted hover:text-text-primary hover:bg-white/[0.1] opacity-0 group-hover/code:opacity-100 transition-all cursor-pointer"
        title={copied ? "Copied!" : "Copy code"}
      >
        {copied ? (
          <Check className="w-3.5 h-3.5 text-green" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
}

// Strip the `node` prop that react-markdown injects before it hits the DOM
const MD_COMPONENTS = {
  pre(props: React.ComponentPropsWithoutRef<"pre"> & { node?: unknown }) {
    return <CodeBlock {...props} />;
  },
};

// ── Chat message ─────────────────────────────────────────────────────

interface Props {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  toolHint?: string;
}

export function ChatMessage({ role, content, isStreaming, toolHint }: Props) {
  const isUser = role === "user";
  const isThinking = isStreaming && !content;

  return (
    <div
      className={cn(
        "flex gap-4 px-4 py-5 md:px-0",
        isUser ? "" : "bg-white/[0.02]"
      )}
    >
      <div className="w-full max-w-3xl mx-auto flex gap-4">
        {/* Avatar */}
        <div
          className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
            isUser
              ? "bg-white/[0.06] border border-white/[0.08]"
              : "bg-green/10 border border-green/20 shadow-[0_0_12px_rgba(17,199,111,0.1)]"
          )}
        >
          {isUser ? (
            <User className="w-4 h-4 text-text-secondary" />
          ) : (
            <Bot className="w-4 h-4 text-green" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-text-muted mb-1.5">
            {isUser ? "You" : "nanobot"}
          </div>

          {isUser ? (
            <div className="text-text-primary leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          ) : isThinking ? (
            <div className="flex items-center gap-3 py-2">
              <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-green/[0.06] border border-green/[0.15] shadow-[0_0_15px_rgba(17,199,111,0.08)]">
                <Loader2 className="w-4 h-4 text-green animate-spin" />
                <span className="text-sm text-green/90 font-medium">Thinking...</span>
              </div>
            </div>
          ) : (
            <div className="markdown-body text-text-primary">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                {content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-2.5 h-5 bg-green ml-0.5 animate-pulse rounded-sm shadow-[0_0_10px_rgba(17,199,111,0.5)]" />
              )}
            </div>
          )}

          {/* Tool hint — fixed height to prevent layout shift */}
          {isStreaming && (
            <div className="h-9 mt-2">
              {toolHint && (
                <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] w-fit animate-fade-in">
                  <Wrench className="w-3.5 h-3.5 text-green/70 animate-spin" />
                  <span className="text-xs text-text-secondary font-medium">{toolHint}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
