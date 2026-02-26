import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PanelWrapper } from "@/components/ui/panel-wrapper";
import {
    getSkills, updateSkills, getCustomSkills, deleteCustomSkill, updateCustomSkill,
    getMcpConfig, updateMcpConfig,
} from "@/lib/api";
import type { CustomSkill, MCPServerConfig } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useStore } from "@/lib/store";
import {
    Blocks, Globe, Terminal, Code2, Database, Search, Trash2, SaveAll,
    MessageSquare, Clock, Brain, FileSearch, ChevronDown, ChevronRight,
    Save, ToggleLeft, ToggleRight, Plus, Network, AlertTriangle,
    MousePointer2, FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Constants ───────────────────────────────────────────────────────

type SkillDef = {
    id: string;
    name: string;
    description: string;
    icon: typeof Globe;
    group: "files" | "web" | "agent" | "desktop";
    warn?: string;
};

const SKILL_GROUPS: { key: string; label: string }[] = [
    { key: "files", label: "Files & Shell" },
    { key: "web", label: "Web" },
    { key: "agent", label: "Agent" },
    { key: "desktop", label: "Desktop" },
];

const AVAILABLE_SKILLS: SkillDef[] = [
    { id: "read_file", name: "File Reader", description: "Read files from the workspace.", icon: Code2, group: "files" },
    { id: "write_file", name: "File Writer", description: "Create files in the workspace.", icon: Blocks, group: "files" },
    { id: "edit_file", name: "File Editor", description: "Modify parts of files in the workspace.", icon: Blocks, group: "files" },
    { id: "list_dir", name: "Directory Inspector", description: "List directory contents.", icon: FolderOpen, group: "files" },
    { id: "exec", name: "Shell Execution", description: "Run terminal commands.", icon: Terminal, group: "files" },
    { id: "web_search", name: "Web Search", description: "Search the web using Brave Search API.", icon: Search, group: "web" },
    { id: "web_fetch", name: "Web Reader", description: "Extract text from public URLs.", icon: Globe, group: "web" },
    { id: "message", name: "Messaging", description: "Send proactive messages to chat channels.", icon: MessageSquare, group: "agent" },
    { id: "save_skill", name: "Skill Creator", description: "Learn new routines and save them.", icon: SaveAll, group: "agent" },
    { id: "save_memory", name: "Memory Save", description: "Save important facts to long-term memory.", icon: Brain, group: "agent" },
    { id: "search_memory", name: "Memory Search", description: "Search past conversations and events.", icon: FileSearch, group: "agent" },
    { id: "cron", name: "Scheduled Tasks", description: "Create and manage automated tasks.", icon: Clock, group: "agent" },
    { id: "computer", name: "Desktop Control", description: "Click, type, scroll, and navigate the graphical desktop.", icon: MousePointer2, group: "desktop", warn: "Grants mouse and keyboard control" },
    { id: "browser", name: "Browser JS", description: "Execute JavaScript in the browser tab — fill forms, read DOM, navigate.", icon: Globe, group: "desktop", warn: "Runs code in the browser" },
];

const MCP_PRESETS: Record<string, { label: string; icon: typeof Globe; config: MCPServerConfig }> = {
    puppeteer: {
        label: "Puppeteer (Browser)",
        icon: Globe,
        config: {
            command: "npx",
            args: ["-y", "@modelcontextprotocol/server-puppeteer"],
            env: {
                PUPPETEER_EXECUTABLE_PATH: "/usr/bin/chromium",
                PUPPETEER_LAUNCH_OPTIONS: '{"headless":false,"args":["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]}',
            },
        },
    },
    filesystem: {
        label: "Filesystem",
        icon: Database,
        config: {
            command: "npx",
            args: ["-y", "@modelcontextprotocol/server-filesystem", "/root/.nanobot/workspace"],
        },
    },
    fetch: {
        label: "Fetch (HTTP)",
        icon: Globe,
        config: {
            command: "npx",
            args: ["-y", "@modelcontextprotocol/server-fetch"],
        },
    },
};

type Tab = "builtin" | "mcp" | "custom";

// ── Sub-components ──────────────────────────────────────────────────

function CollapsibleGroup({ label, children, count, defaultOpen = false }: {
    label: string;
    children: React.ReactNode;
    count?: number;
    defaultOpen?: boolean;
}) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="border border-white/[0.06] rounded-lg overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-3 py-2.5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors cursor-pointer"
            >
                <div className="flex items-center gap-2">
                    {open
                        ? <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
                        : <ChevronRight className="w-3.5 h-3.5 text-text-muted" />
                    }
                    <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">{label}</span>
                </div>
                {count !== undefined && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green/15 text-green font-medium">
                        {count}
                    </span>
                )}
            </button>
            {open && (
                <div className="p-2 space-y-1.5 border-t border-white/[0.04]">
                    {children}
                </div>
            )}
        </div>
    );
}

function SkillEditor({ skill, onSave, onDelete }: {
    skill: CustomSkill;
    onSave: (name: string, data: Partial<CustomSkill>) => Promise<void>;
    onDelete: (name: string) => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const [content, setContent] = useState(skill.content);
    const [saving, setSaving] = useState(false);
    const [dirty, setDirty] = useState(false);

    useEffect(() => {
        setContent(skill.content);
        setDirty(false);
    }, [skill.content]);

    const handleSave = async () => {
        setSaving(true);
        await onSave(skill.name, { content });
        setDirty(false);
        setSaving(false);
    };

    const handleToggleEnabled = async () => {
        const newEnabled = skill.enabled ? 0 : 1;
        await onSave(skill.name, { enabled: newEnabled });
    };

    const isEnabled = skill.enabled === 1;

    return (
        <div className={cn(
            "rounded-xl border transition-all duration-200",
            isEnabled
                ? "bg-white/[0.03] border-white/[0.06] hover:border-white/[0.1]"
                : "bg-white/[0.01] border-white/[0.04] opacity-70"
        )}>
            <div
                className="flex items-start justify-between p-4 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="p-2 rounded-lg bg-white/[0.04] text-text-muted shrink-0">
                        <Blocks className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <span className="text-sm font-semibold text-text-primary truncate">
                            {skill.name}
                        </span>
                        <span className="text-xs text-text-muted mt-0.5 line-clamp-1">
                            {skill.description || "No description"}
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => { e.stopPropagation(); handleToggleEnabled(); }}
                        title={isEnabled ? "Disable" : "Enable"}
                    >
                        {isEnabled
                            ? <ToggleRight className="w-4 h-4 text-green" />
                            : <ToggleLeft className="w-4 h-4 text-text-muted" />
                        }
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-500/70 hover:text-red-500 hover:bg-red-500/10"
                        onClick={(e) => { e.stopPropagation(); onDelete(skill.name); }}
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                    {expanded
                        ? <ChevronDown className="w-4 h-4 text-text-muted" />
                        : <ChevronRight className="w-4 h-4 text-text-muted" />
                    }
                </div>
            </div>

            {expanded && (
                <div className="px-4 pb-4 space-y-3 border-t border-white/[0.04] pt-3">
                    <label className="block text-xs text-text-secondary">Skill Content (Markdown)</label>
                    <Textarea
                        value={content}
                        onChange={(e) => { setContent(e.target.value); setDirty(true); }}
                        className="font-mono text-xs min-h-[200px] resize-y"
                        placeholder="---\ndescription: My skill\nalways: false\n---\nInstructions..."
                    />
                    {dirty && (
                        <div className="flex justify-end">
                            <Button
                                size="sm"
                                className="h-7 text-xs px-3"
                                onClick={handleSave}
                                disabled={saving}
                            >
                                <Save className="w-3 h-3 mr-1" />
                                {saving ? "Saving..." : "Save Changes"}
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function McpServerCard({ name, config, onDelete }: {
    name: string;
    config: MCPServerConfig;
    onDelete: (name: string) => void;
}) {
    return (
        <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.03] border border-white/[0.06] group hover:bg-white/[0.05] hover:border-white/[0.1] transition-all">
            <div className="flex items-center gap-3 min-w-0">
                <div className="p-1.5 rounded-lg bg-green/10 text-green shrink-0">
                    <Terminal className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">{name}</p>
                    <p className="text-[10px] text-text-muted font-mono truncate">
                        {config.command} {config.args?.join(" ")}
                    </p>
                </div>
            </div>
            <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-red-500/50 hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                onClick={() => onDelete(name)}
            >
                <Trash2 className="w-3.5 h-3.5" />
            </Button>
        </div>
    );
}

// ── Main component ──────────────────────────────────────────────────

export function SkillsPanel() {
    const { skillsOpen, setPanelState } = useStore();
    const [tab, setTab] = useState<Tab>("builtin");

    // Built-in skills state
    const [enabledSkills, setEnabledSkills] = useState<string[]>([]);
    // Custom skills state
    const [customSkills, setCustomSkills] = useState<CustomSkill[]>([]);
    // MCP state
    const [mcpServers, setMcpServers] = useState<Record<string, MCPServerConfig>>({});
    const [mcpDirty, setMcpDirty] = useState(false);
    const [mcpSaving, setMcpSaving] = useState<string | null>(null);
    const [showCustomMcp, setShowCustomMcp] = useState(false);
    const [customMcpName, setCustomMcpName] = useState("");
    const [customMcpCommand, setCustomMcpCommand] = useState("");
    const [customMcpArgs, setCustomMcpArgs] = useState("");

    const [loading, setLoading] = useState(false);

    const loadAll = async () => {
        setLoading(true);
        try {
            const [skillsRes, customRes, mcpRes] = await Promise.all([
                getSkills(),
                getCustomSkills(),
                getMcpConfig(),
            ]);
            setEnabledSkills(skillsRes.tools_enabled || []);
            setCustomSkills(customRes || []);
            setMcpServers(mcpRes.mcpServers || {});
            setMcpDirty(false);
        } catch (e) {
            toast("error", `Failed to load skills: ${(e as Error).message}`);
        }
        setLoading(false);
    };

    useEffect(() => {
        if (skillsOpen) loadAll();
    }, [skillsOpen]);

    // ── Built-in skills ─────────────────────────────────────────────

    const toggleSkill = async (skillId: string) => {
        const isEnabled = enabledSkills.includes(skillId);
        const newSkills = isEnabled
            ? enabledSkills.filter((id) => id !== skillId)
            : [...enabledSkills, skillId];
        setEnabledSkills(newSkills);
        try {
            await updateSkills(newSkills);
        } catch (e) {
            setEnabledSkills(enabledSkills);
            toast("error", `Failed to toggle skill: ${(e as Error).message}`);
        }
    };

    // ── Custom skills ───────────────────────────────────────────────

    const handleDeleteCustomSkill = async (name: string) => {
        try {
            await deleteCustomSkill(name);
            setCustomSkills((prev) => prev.filter((s) => s.name !== name));
            toast("success", `Skill "${name}" deleted`);
        } catch (e) {
            toast("error", `Failed to delete: ${(e as Error).message}`);
        }
    };

    const handleSaveCustomSkill = async (name: string, data: Partial<CustomSkill>) => {
        try {
            await updateCustomSkill(name, data);
            setCustomSkills((prev) =>
                prev.map((s) => s.name === name ? { ...s, ...data } : s)
            );
            toast("success", "Skill updated");
        } catch (e) {
            toast("error", `Failed to save: ${(e as Error).message}`);
        }
    };

    // ── MCP ─────────────────────────────────────────────────────────

    const addMcpPreset = (key: string) => {
        const preset = MCP_PRESETS[key];
        if (preset && !mcpServers[key]) {
            setMcpServers((prev) => ({ ...prev, [key]: preset.config }));
            setMcpDirty(true);
        }
    };

    const addCustomMcp = () => {
        if (!customMcpName.trim() || !customMcpCommand.trim()) return;
        const args = customMcpArgs.trim() ? customMcpArgs.split(/\s+/) : [];
        setMcpServers((prev) => ({
            ...prev,
            [customMcpName.trim()]: { command: customMcpCommand.trim(), args },
        }));
        setCustomMcpName("");
        setCustomMcpCommand("");
        setCustomMcpArgs("");
        setShowCustomMcp(false);
        setMcpDirty(true);
    };

    const removeMcp = (name: string) => {
        setMcpServers((prev) => {
            const next = { ...prev };
            delete next[name];
            return next;
        });
        setMcpDirty(true);
    };

    const saveMcp = async () => {
        setMcpSaving("Saving...");
        try {
            await updateMcpConfig({ mcpServers });
            setMcpDirty(false);
            setMcpSaving("Saved!");
            toast("success", "MCP configuration saved");
            setTimeout(() => setMcpSaving(null), 2000);
        } catch (e) {
            setMcpSaving("Error");
            toast("error", `Failed to save MCP: ${(e as Error).message}`);
            setTimeout(() => setMcpSaving(null), 2000);
        }
    };

    const mcpEntries = Object.entries(mcpServers);
    const availablePresets = Object.entries(MCP_PRESETS).filter(([k]) => !mcpServers[k]);

    // Tab order: Built-in → MCP → Custom
    const TABS: { key: Tab; label: string; count?: number }[] = [
        { key: "builtin", label: "Built-in", count: enabledSkills.length },
        { key: "mcp", label: "MCP", count: mcpEntries.length },
        { key: "custom", label: "Custom", count: customSkills.length },
    ];

    return (
        <PanelWrapper
            open={skillsOpen}
            onClose={() => setPanelState("skills", false)}
            title="Agent Skills"
            icon={Blocks}
            maxWidth="max-w-xl"
        >
            {/* Tabs */}
            <div className="flex gap-1 bg-white/[0.04] rounded-lg p-1 mx-5 my-4">
                {TABS.map(({ key, label, count }) => (
                    <button
                        key={key}
                        onClick={() => setTab(key)}
                        className={cn(
                            "flex-1 rounded-md px-3 py-2.5 text-sm transition-colors cursor-pointer",
                            tab === key
                                ? "bg-white/[0.08] text-text-primary font-medium"
                                : "text-text-muted hover:text-text-primary"
                        )}
                    >
                        <span className="flex items-center justify-center gap-1.5">
                            {label}
                            {(count !== undefined && count > 0) && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green/20 text-green">
                                    {count}
                                </span>
                            )}
                        </span>
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-5">
                {loading ? (
                    <div className="flex items-center justify-center p-8">
                        <div className="w-6 h-6 border-2 border-green/30 border-t-green rounded-full animate-spin" />
                    </div>
                ) : (
                    <>
                        {/* ── Built-in Tools (collapsible groups) ── */}
                        {tab === "builtin" && (
                            <div className="space-y-2.5">
                                {SKILL_GROUPS.map((group) => {
                                    const skills = AVAILABLE_SKILLS.filter((s) => s.group === group.key);
                                    if (skills.length === 0) return null;
                                    const activeCount = skills.filter((s) => enabledSkills.includes(s.id)).length;
                                    return (
                                        <CollapsibleGroup
                                            key={group.key}
                                            label={group.label}
                                            count={activeCount}
                                            defaultOpen={activeCount > 0}
                                        >
                                            {skills.map((skill) => {
                                                const Icon = skill.icon;
                                                const active = enabledSkills.includes(skill.id);
                                                const isDesktop = !!skill.warn;
                                                return (
                                                    <div
                                                        key={skill.id}
                                                        onClick={() => toggleSkill(skill.id)}
                                                        className={cn(
                                                            "group flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-all duration-200",
                                                            isDesktop && active
                                                                ? "bg-yellow-muted border-yellow/30"
                                                                : active
                                                                    ? "bg-green/[0.08] border-green/20"
                                                                    : "bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.05] hover:border-white/[0.08]"
                                                        )}
                                                    >
                                                        <div className="flex items-center gap-2.5">
                                                            <div className={cn(
                                                                "p-1.5 rounded-md transition-colors",
                                                                isDesktop && active
                                                                    ? "bg-yellow text-black"
                                                                    : active
                                                                        ? "bg-green text-black"
                                                                        : "bg-white/[0.04] text-text-muted group-hover:text-text-primary"
                                                            )}>
                                                                <Icon className="w-3.5 h-3.5" />
                                                            </div>
                                                            <div className="flex flex-col">
                                                                <span className={cn(
                                                                    "text-sm font-medium transition-colors leading-tight",
                                                                    isDesktop && active ? "text-yellow" : active ? "text-green-light" : "text-text-primary"
                                                                )}>
                                                                    {skill.name}
                                                                </span>
                                                                <span className="text-[10px] text-text-muted leading-tight mt-0.5">
                                                                    {skill.description}
                                                                </span>
                                                                {isDesktop && active && (
                                                                    <span className="flex items-center gap-1 text-[10px] text-yellow/80 mt-0.5">
                                                                        <AlertTriangle className="w-3 h-3" />
                                                                        {skill.warn}
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>

                                                        <div className={cn(
                                                            "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors duration-200",
                                                            isDesktop && active ? "bg-yellow" : active ? "bg-green" : "bg-white/[0.06]"
                                                        )}>
                                                            <span className={cn(
                                                                "inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition duration-200",
                                                                active ? "translate-x-4" : "translate-x-0"
                                                            )} />
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </CollapsibleGroup>
                                    );
                                })}
                            </div>
                        )}

                        {/* ── MCP Integrations (now second tab) ── */}
                        {tab === "mcp" && (
                            <div className="space-y-4">
                                <p className="text-xs text-text-muted leading-relaxed">
                                    MCP servers extend the agent with external tools and capabilities.
                                </p>

                                {/* Active MCP servers */}
                                {mcpEntries.length > 0 ? (
                                    <div className="space-y-2">
                                        {mcpEntries.map(([name, cfg]) => (
                                            <McpServerCard key={name} name={name} config={cfg} onDelete={removeMcp} />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-10 text-text-muted">
                                        <Network className="w-8 h-8 mx-auto mb-2 opacity-30" />
                                        <p className="text-xs">No MCP servers configured. Add one below.</p>
                                    </div>
                                )}

                                {/* Quick-add presets */}
                                {availablePresets.length > 0 && (
                                    <div>
                                        <label className="block text-xs text-text-muted uppercase tracking-wider mb-2">Quick Add</label>
                                        <div className="flex flex-wrap gap-2">
                                            {availablePresets.map(([key, preset]) => {
                                                const Icon = preset.icon;
                                                return (
                                                    <Button
                                                        key={key}
                                                        type="button"
                                                        variant="outline"
                                                        size="sm"
                                                        className="h-7 text-[11px] px-2.5 gap-1.5"
                                                        onClick={() => addMcpPreset(key)}
                                                    >
                                                        <Icon className="w-3 h-3" />
                                                        {preset.label}
                                                    </Button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}

                                {/* Custom MCP add */}
                                {showCustomMcp ? (
                                    <div className="space-y-2 p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                                        <Input
                                            value={customMcpName}
                                            onChange={(e) => setCustomMcpName(e.target.value)}
                                            placeholder="Server name (e.g. my-mcp)"
                                            className="text-xs h-8"
                                        />
                                        <Input
                                            value={customMcpCommand}
                                            onChange={(e) => setCustomMcpCommand(e.target.value)}
                                            placeholder="Command (e.g. npx)"
                                            className="text-xs h-8"
                                        />
                                        <Input
                                            value={customMcpArgs}
                                            onChange={(e) => setCustomMcpArgs(e.target.value)}
                                            placeholder="Arguments (space-separated)"
                                            className="text-xs h-8"
                                        />
                                        <div className="flex gap-2 justify-end">
                                            <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setShowCustomMcp(false)}>
                                                Cancel
                                            </Button>
                                            <Button type="button" size="sm" className="h-7 text-xs" onClick={addCustomMcp}>
                                                Add
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="h-7 text-[11px] gap-1.5 w-full"
                                        onClick={() => setShowCustomMcp(true)}
                                    >
                                        <Plus className="w-3 h-3" />
                                        Add Custom MCP Server
                                    </Button>
                                )}

                                {/* MCP Save */}
                                {mcpDirty && (
                                    <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                                        <span className="text-xs text-text-muted">Unsaved changes</span>
                                        <Button size="sm" className="h-7 text-xs px-3" onClick={saveMcp}>
                                            <Save className="w-3 h-3 mr-1" />
                                            {mcpSaving || "Save MCP"}
                                        </Button>
                                    </div>
                                )}
                                {!mcpDirty && mcpSaving && (
                                    <p className="text-xs text-green text-center">{mcpSaving}</p>
                                )}
                            </div>
                        )}

                        {/* ── Custom Skills (now last tab) ── */}
                        {tab === "custom" && (
                            <div className="space-y-4">
                                <p className="text-xs text-text-muted leading-relaxed">
                                    Procedures the agent has learned from conversations. Click to expand, edit, or disable.
                                </p>
                                {customSkills.length === 0 ? (
                                    <div className="text-center py-10 text-text-muted">
                                        <Blocks className="w-8 h-8 mx-auto mb-2 opacity-30" />
                                        <p className="text-xs">No custom skills yet. Teach the bot new procedures and they'll appear here.</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {customSkills.map((skill) => (
                                            <SkillEditor
                                                key={skill.name}
                                                skill={skill}
                                                onSave={handleSaveCustomSkill}
                                                onDelete={handleDeleteCustomSkill}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
        </PanelWrapper>
    );
}
