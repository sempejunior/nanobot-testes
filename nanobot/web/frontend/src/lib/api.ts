const API_BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("nanobot_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// Auth
export interface User {
  user_id: string;
  display_name: string;
  email: string | null;
  status: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export async function register(user_id: string, display_name?: string, email?: string): Promise<AuthResponse> {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ user_id, display_name, email }),
  });
}

export async function login(user_id: string): Promise<AuthResponse> {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ user_id }),
  });
}

export async function getMe(): Promise<User> {
  return request("/me");
}

// Sessions
export interface Session {
  session_key: string;
  title: string;
  message_count: number;
  updated_at: string;
}

export interface Message {
  role: string;
  content: string;
}

export async function listSessions(): Promise<Session[]> {
  return request("/sessions");
}

export async function getMessages(sessionKey: string): Promise<Message[]> {
  return request(`/sessions/${encodeURIComponent(sessionKey)}/messages`);
}

export async function deleteSession(sessionKey: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${encodeURIComponent(sessionKey)}`, { method: "DELETE" });
}

// Cron
export interface CronJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule_kind: string;
  schedule_expr: string;
  message: string;
}

export async function listCronJobs(): Promise<CronJob[]> {
  return request("/cron");
}

export async function addCronJob(data: {
  name: string;
  message: string;
  kind: string;
  every_seconds?: number;
  expr?: string;
  tz?: string;
}): Promise<{ id: string; name: string }> {
  return request("/cron", { method: "POST", body: JSON.stringify(data) });
}

export async function deleteCronJob(jobId: string): Promise<{ ok: boolean }> {
  return request(`/cron/${jobId}`, { method: "DELETE" });
}

// Config
export interface AgentConfig {
  model?: string;
  max_tokens?: number;
  temperature?: number;
  max_tool_iterations?: number;
  memory_window?: number;
  language?: string;
  custom_instructions?: string;
}

export async function getConfig(): Promise<AgentConfig> {
  return request("/config");
}

export async function updateConfig(data: Partial<AgentConfig>): Promise<{ ok: boolean; agent_config: AgentConfig }> {
  return request("/config", { method: "PUT", body: JSON.stringify(data) });
}

// Provider
export interface ProviderConfig {
  name: string;      // "openai" | "anthropic" | "custom" | ""
  api_key: string;   // masked on GET
  api_base: string;
}

export async function getProviderConfig(): Promise<ProviderConfig> {
  return request("/config/provider");
}

export async function updateProviderConfig(data: ProviderConfig): Promise<{ ok: boolean }> {
  return request("/config/provider", { method: "PUT", body: JSON.stringify(data) });
}

// Skills
export interface SkillsData {
  tools_enabled: string[];
}

export async function getSkills(): Promise<SkillsData> {
  return request("/skills");
}

export async function updateSkills(tools_enabled: string[]): Promise<{ ok: boolean; tools_enabled: string[] }> {
  return request("/skills", { method: "PUT", body: JSON.stringify({ tools_enabled }) });
}

export interface CustomSkill {
  name: string;
  description: string;
  content: string;
  always_active: number;
  enabled: number;
}

// MCP Configuration
export interface MCPServerConfig {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  tool_timeout?: number;
}

export interface MCPData {
  mcpServers: Record<string, MCPServerConfig>;
}

export async function getMcpConfig(): Promise<MCPData> {
  return request("/config/mcp");
}

export async function updateMcpConfig(data: MCPData): Promise<{ ok: boolean }> {
  return request("/config/mcp", { method: "PUT", body: JSON.stringify(data) });
}

export async function getCustomSkills(): Promise<CustomSkill[]> {
  return request("/skills/custom");
}

export async function deleteCustomSkill(name: string): Promise<void> {
  return request(`/skills/custom/${name}`, { method: "DELETE" });
}

export async function updateCustomSkill(name: string, data: {
  content?: string;
  description?: string;
  always_active?: number;
  enabled?: number;
}): Promise<{ ok: boolean }> {
  return request(`/skills/custom/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// Memory
export interface MemoryHistoryEntry {
  id: number;
  content: string;
  created_at: string;
}

export interface MemoryData {
  long_term: string;
  history: MemoryHistoryEntry[];
}

export async function getMemory(): Promise<MemoryData> {
  return request("/memory");
}

export async function updateLongTermMemory(content: string): Promise<{ ok: boolean }> {
  return request("/memory/long_term", { method: "PUT", body: JSON.stringify({ content }) });
}

export async function clearMemoryHistory(): Promise<{ ok: boolean; deleted: number }> {
  return request("/memory", { method: "DELETE" });
}

export async function deleteMemoryHistoryEntry(entryId: number): Promise<{ ok: boolean }> {
  return request(`/memory/${entryId}`, { method: "DELETE" });
}

// Memory search
export interface MemorySearchResult {
  id: number;
  content: string;
  created_at: string;
  relevance?: number;
}

export async function searchMemory(query: string): Promise<{ results: MemorySearchResult[] }> {
  return request(`/memory/search?q=${encodeURIComponent(query)}`);
}

// WebSocket
export type WsMessageType = "response" | "progress" | "tool_hint" | "error" | "pong";

export interface WsIncoming {
  type: WsMessageType;
  content?: string;
  session_key?: string;
}

export function createChatSocket(token: string): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}/ws/chat?token=${encodeURIComponent(token)}`);
}
