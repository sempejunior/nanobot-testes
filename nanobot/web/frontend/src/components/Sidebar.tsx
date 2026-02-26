import { useEffect, useState, useMemo } from "react";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import {
  Plus,
  MessageSquare,
  Trash2,
  LogOut,
  X,
  User,
  Settings,
  Brain,
  Blocks,
  Clock,
  Bot,
  Search,
  SquarePen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { key: "new-chat" as const, label: "New Chat", icon: SquarePen },
  { key: "memory" as const, label: "Memory", icon: Brain },
  { key: "skills" as const, label: "Skills & MCP", icon: Blocks },
  { key: "cron" as const, label: "Scheduler", icon: Clock },
  { key: "settings" as const, label: "Settings", icon: Settings },
];

export function Sidebar() {
  const {
    user,
    sessions,
    activeSessionKey,
    sidebarOpen,
    loadSessions,
    selectSession,
    newChat,
    removeSession,
    logout,
    toggleSidebar,
    setPanelState,
  } = useStore();

  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const filteredSessions = useMemo(() => {
    const sorted = [...sessions].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    if (!searchTerm) return sorted;
    const q = searchTerm.toLowerCase();
    return sorted.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchTerm]);

  const handleNavClick = (key: string) => {
    if (key === "new-chat") {
      newChat();
    } else {
      setPanelState(key as "memory" | "skills" | "cron" | "settings", true);
    }
  };

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 md:hidden animate-fade-in"
          onClick={toggleSidebar}
        />
      )}

      <aside
        className={cn(
          "fixed md:relative z-50 md:z-auto",
          "flex flex-col h-full w-[268px] bg-surface border-r border-border",
          "transition-transform duration-200 ease-in-out",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden"
        )}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-green/10 border border-green/20 flex items-center justify-center">
              <Bot className="w-4.5 h-4.5 text-green" />
            </div>
            <span className="text-[15px] font-semibold text-text-primary tracking-tight">nanobot</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="md:hidden h-8 w-8"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* ── Navigation / Actions ── */}
        <nav className="px-3 pb-4 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => handleNavClick(item.key)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-white/[0.06] transition-all duration-150 cursor-pointer"
              >
                <Icon className="w-[18px] h-[18px] shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* ── Divider ── */}
        <div className="mx-4 border-t border-border" />

        {/* ── Chat History ── */}
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <span className="text-xs font-medium text-text-muted">Your chats</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={newChat}
            title="New Chat"
            className="h-6 w-6 text-text-muted hover:text-text-primary"
          >
            <Plus className="w-3.5 h-3.5" />
          </Button>
        </div>

        {/* Search — show when more than 3 sessions */}
        {sessions.length > 3 && (
          <div className="px-3 mb-1">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search chats..."
                className="w-full h-8 pl-8 pr-2 text-xs bg-white/[0.03] border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-green/40 transition-colors"
              />
            </div>
          </div>
        )}

        {/* Session List */}
        <div className="flex-1 overflow-y-auto px-2 py-1">
          {filteredSessions.length === 0 ? (
            <div className="px-3 py-6 text-center text-text-muted text-xs">
              {searchTerm ? "No matching chats" : "No conversations yet"}
            </div>
          ) : (
            filteredSessions.map((session) => (
              <div
                key={session.session_key}
                className={cn(
                  "group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer",
                  "transition-all duration-150 text-sm",
                  activeSessionKey === session.session_key
                    ? "bg-green/[0.1] text-green-light"
                    : "text-text-secondary hover:bg-white/[0.04] hover:text-text-primary"
                )}
                onClick={() => selectSession(session.session_key)}
              >
                <MessageSquare className="w-4 h-4 shrink-0 opacity-50" />
                <span className="flex-1 truncate">{session.title}</span>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-muted hover:text-red transition-all cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeSession(session.session_key);
                  }}
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* ── User Footer ── */}
        <div className="border-t border-border px-3 py-3">
          <div className="flex items-center gap-3 px-1">
            <div className="w-8 h-8 rounded-full bg-green/15 flex items-center justify-center shrink-0">
              <User className="w-4 h-4 text-green" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text-primary truncate leading-tight">
                {user?.display_name || user?.user_id}
              </div>
              <div className="text-[11px] text-text-muted truncate leading-tight">
                {user?.email || user?.user_id}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Logout"
              className="shrink-0 h-8 w-8 text-text-muted hover:text-text-primary"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
}
