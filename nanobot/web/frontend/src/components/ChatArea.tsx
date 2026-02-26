import { useEffect, useRef } from "react";
import { useStore } from "@/lib/store";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { Button } from "@/components/ui/button";
import { Bot, Menu, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

export function ChatArea() {
  const { messages, activeSessionKey, sidebarOpen, toggleSidebar, newChat, sending, connected } =
    useStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const isEmpty = messages.length === 0 && !sending;
  const lastMsg = messages[messages.length - 1];
  const needsThinkingBubble =
    sending && (!lastMsg || lastMsg.role !== "assistant" || !lastMsg.isStreaming);

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full">
      {/* Top bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-white/[0.02] backdrop-blur-md">
        {!sidebarOpen && (
          <Button variant="ghost" size="icon" onClick={toggleSidebar}>
            <Menu className="w-5 h-5" />
          </Button>
        )}
        <div className="flex-1 flex items-center gap-2">
          <Bot className="w-5 h-5 text-green" />
          <span className="text-sm font-medium text-text-primary">
            {activeSessionKey ? "Chat" : "New Chat"}
          </span>
          {/* Connection status indicator */}
          <div
            className={cn(
              "w-2 h-2 rounded-full transition-colors",
              connected
                ? "bg-green shadow-[0_0_6px_rgba(17,199,111,0.5)]"
                : "bg-yellow animate-pulse"
            )}
            title={connected ? "Connected" : "Reconnecting..."}
          />
        </div>
        <Button variant="ghost" size="icon" onClick={newChat} title="New Chat">
          <Plus className="w-5 h-5" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full px-4 text-center">
            <div className="w-20 h-20 rounded-3xl bg-green/10 border border-green/20 flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(17,199,111,0.15)]">
              <Bot className="w-10 h-10 text-green" />
            </div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">
              How can I help you?
            </h2>
            <p className="text-text-secondary text-sm max-w-md">
              Ask me anything. I can help with research, coding, writing,
              analysis, and much more.
            </p>
          </div>
        ) : (
          <div>
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                isStreaming={msg.isStreaming}
                toolHint={msg.toolHint}
              />
            ))}
            {needsThinkingBubble && (
              <ChatMessage
                role="assistant"
                content=""
                isStreaming
              />
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput />
    </div>
  );
}
