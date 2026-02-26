import { create } from "zustand";
import type { User, Session, Message, WsIncoming } from "./api";
import {
  login as apiLogin,
  register as apiRegister,
  getMe,
  listSessions,
  getMessages,
  deleteSession as apiDeleteSession,
  createChatSocket,
} from "./api";
import { toast } from "./toast";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  toolHint?: string;
}

interface AppState {
  // Auth
  user: User | null;
  token: string | null;
  authLoading: boolean;
  authError: string | null;

  // Sessions
  sessions: Session[];
  activeSessionKey: string | null;
  messages: ChatMessage[];
  loadingSessions: boolean;

  // Chat
  ws: WebSocket | null;
  connected: boolean;
  sending: boolean;

  // Sidebar & Navigation Panels
  sidebarOpen: boolean;
  settingsOpen: boolean;
  skillsOpen: boolean;
  memoryOpen: boolean;
  cronOpen: boolean;

  // Actions
  initAuth: () => Promise<void>;
  login: (userId: string) => Promise<void>;
  register: (userId: string, displayName?: string, email?: string) => Promise<void>;
  logout: () => void;

  loadSessions: () => Promise<void>;
  selectSession: (key: string) => Promise<void>;
  newChat: () => void;
  removeSession: (key: string) => Promise<void>;

  connectWs: () => void;
  disconnectWs: () => void;
  sendMessage: (content: string) => void;

  toggleSidebar: () => void;
  setPanelState: (panel: "settings" | "skills" | "memory" | "cron", open: boolean) => void;
}

let msgCounter = 0;
function nextId(): string {
  return `msg_${Date.now()}_${++msgCounter}`;
}

export const useStore = create<AppState>((set, get) => ({
  user: null,
  token: localStorage.getItem("nanobot_token"),
  authLoading: false,
  authError: null,

  sessions: [],
  activeSessionKey: null,
  messages: [],
  loadingSessions: false,

  ws: null,
  connected: false,
  sending: false,

  sidebarOpen: true,
  settingsOpen: false,
  skillsOpen: false,
  memoryOpen: false,
  cronOpen: false,

  // ---- Auth ----

  async initAuth() {
    const token = get().token;
    if (!token) return;
    set({ authLoading: true });
    try {
      const user = await getMe();
      set({ user, authLoading: false });
      get().connectWs();
      get().loadSessions();
    } catch {
      localStorage.removeItem("nanobot_token");
      set({ token: null, user: null, authLoading: false });
    }
  },

  async login(userId: string) {
    set({ authLoading: true, authError: null });
    try {
      const res = await apiLogin(userId);
      localStorage.setItem("nanobot_token", res.token);
      set({ token: res.token, user: res.user, authLoading: false });
      get().connectWs();
      get().loadSessions();
    } catch (e) {
      set({ authError: (e as Error).message, authLoading: false });
    }
  },

  async register(userId: string, displayName?: string, email?: string) {
    set({ authLoading: true, authError: null });
    try {
      const res = await apiRegister(userId, displayName, email);
      localStorage.setItem("nanobot_token", res.token);
      set({ token: res.token, user: res.user, authLoading: false });
      get().connectWs();
      get().loadSessions();
    } catch (e) {
      set({ authError: (e as Error).message, authLoading: false });
    }
  },

  logout() {
    get().disconnectWs();
    localStorage.removeItem("nanobot_token");
    set({
      user: null,
      token: null,
      sessions: [],
      activeSessionKey: null,
      messages: [],
    });
  },

  // ---- Sessions ----

  async loadSessions() {
    set({ loadingSessions: true });
    try {
      const sessions = await listSessions();
      set({ sessions, loadingSessions: false });
    } catch (e) {
      set({ loadingSessions: false });
      toast("error", `Failed to load sessions: ${(e as Error).message}`);
    }
  },

  async selectSession(key: string) {
    set({ activeSessionKey: key, messages: [] });
    try {
      const msgs = await getMessages(key);
      const chatMsgs: ChatMessage[] = msgs.map((m: Message) => ({
        id: nextId(),
        role: m.role as "user" | "assistant",
        content: m.content,
      }));
      set({ messages: chatMsgs });
    } catch (e) {
      toast("error", `Failed to load messages: ${(e as Error).message}`);
    }
  },

  newChat() {
    set({ activeSessionKey: null, messages: [] });
  },

  async removeSession(key: string) {
    await apiDeleteSession(key);
    const { sessions, activeSessionKey } = get();
    set({
      sessions: sessions.filter((s) => s.session_key !== key),
      ...(activeSessionKey === key ? { activeSessionKey: null, messages: [] } : {}),
    });
  },

  // ---- WebSocket ----

  connectWs() {
    const { token, ws: existingWs } = get();
    if (!token) return;
    if (existingWs) existingWs.close();

    const ws = createChatSocket(token);

    ws.onopen = () => {
      set({ connected: true });
      // Ping every 30s
      const interval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        } else {
          clearInterval(interval);
        }
      }, 30000);
    };

    ws.onmessage = (evt) => {
      const data: WsIncoming = JSON.parse(evt.data);
      const { messages } = get();

      if (data.type === "progress") {
        // Update the last assistant message with streaming content
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.isStreaming) {
          set({
            messages: messages.map((m) =>
              m.id === last.id ? { ...m, content: data.content || "" } : m
            ),
          });
        } else {
          set({
            messages: [
              ...messages,
              {
                id: nextId(),
                role: "assistant",
                content: data.content || "",
                isStreaming: true,
              },
            ],
          });
        }
      } else if (data.type === "tool_hint") {
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.isStreaming) {
          set({
            messages: messages.map((m) =>
              m.id === last.id ? { ...m, toolHint: data.content || "" } : m
            ),
          });
        }
      } else if (data.type === "response") {
        // Replace streaming message with final response
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.isStreaming) {
          set({
            messages: messages.map((m) =>
              m.id === last.id
                ? { ...m, content: data.content || "", isStreaming: false, toolHint: undefined }
                : m
            ),
            sending: false,
            activeSessionKey: data.session_key || get().activeSessionKey,
          });
        } else {
          set({
            messages: [
              ...messages,
              { id: nextId(), role: "assistant", content: data.content || "" },
            ],
            sending: false,
            activeSessionKey: data.session_key || get().activeSessionKey,
          });
        }
        // Refresh sessions list
        get().loadSessions();
      } else if (data.type === "error") {
        set({
          messages: [
            ...messages,
            { id: nextId(), role: "assistant", content: `Error: ${data.content}` },
          ],
          sending: false,
        });
      }
    };

    ws.onclose = () => {
      set({ connected: false });
      // Auto-reconnect after 3s
      setTimeout(() => {
        if (get().token) get().connectWs();
      }, 3000);
    };

    set({ ws });
  },

  disconnectWs() {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null, connected: false });
    }
  },

  sendMessage(content: string) {
    const { ws, activeSessionKey, messages } = get();
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const sessionKey = activeSessionKey || `web:${crypto.randomUUID().slice(0, 12)}`;

    const userMsg: ChatMessage = {
      id: nextId(),
      role: "user",
      content,
    };

    set({
      messages: [...messages, userMsg],
      sending: true,
      activeSessionKey: sessionKey,
    });

    ws.send(
      JSON.stringify({
        type: "message",
        content,
        session_key: sessionKey,
      })
    );
  },

  toggleSidebar() {
    set({ sidebarOpen: !get().sidebarOpen });
  },

  setPanelState(panel, open) {
    set({ [`${panel}Open`]: open } as Partial<AppState>);
  },
}));
