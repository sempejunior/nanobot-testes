import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PanelWrapper } from "@/components/ui/panel-wrapper";
import { getConfig, updateConfig, getProviderConfig, updateProviderConfig } from "@/lib/api";
import type { AgentConfig, ProviderConfig } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useStore } from "@/lib/store";
import {
    Settings,
    Save,
    Cpu,
    Eye,
    EyeOff,
    MessageSquareText,
    ChevronDown,
    Check,
    SlidersHorizontal,
} from "lucide-react";

const LANGUAGES = [
    { value: "", label: "Auto (server default)" },
    { value: "Português (Brasil)", label: "Português (Brasil)" },
    { value: "English", label: "English" },
    { value: "Español", label: "Español" },
    { value: "Français", label: "Français" },
    { value: "Deutsch", label: "Deutsch" },
    { value: "Italiano", label: "Italiano" },
    { value: "日本語", label: "日本語" },
    { value: "中文", label: "中文" },
    { value: "한국어", label: "한국어" },
];

type Tab = "general" | "model" | "advanced";

const TABS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: "general", label: "General", icon: MessageSquareText },
    { id: "model", label: "Model", icon: Cpu },
    { id: "advanced", label: "Advanced", icon: SlidersHorizontal },
];

function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
    return (
        <div className="mb-2">
            <label className="text-sm font-medium text-text-secondary">{children}</label>
            {hint && <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{hint}</p>}
        </div>
    );
}

function TabGeneral({ config, onChange }: {
    config: AgentConfig;
    onChange: (key: keyof AgentConfig, value: string | number) => void;
}) {
    return (
        <div className="space-y-6">
            <div>
                <FieldLabel hint="Tell the agent about yourself, your preferences, or how it should behave.">
                    Custom Instructions
                </FieldLabel>
                <textarea
                    value={config.custom_instructions || ""}
                    onChange={(e) => onChange("custom_instructions", e.target.value)}
                    placeholder={"Example:\n- I'm a backend developer working with Python and FastAPI\n- Always explain your reasoning before acting\n- Prefer concise answers"}
                    rows={5}
                    className="w-full resize-none text-sm leading-relaxed bg-glass border border-glass-border rounded-lg p-3.5 text-text-primary placeholder:text-text-muted/40 focus:outline-none focus:border-green/30 transition-colors"
                />
            </div>

            <div>
                <FieldLabel hint="Choose the language the agent should use when responding.">
                    Response Language
                </FieldLabel>
                <div className="relative">
                    <select
                        value={config.language || ""}
                        onChange={(e) => onChange("language", e.target.value)}
                        className="w-full h-10 px-3 pr-8 text-sm bg-glass border border-glass-border rounded-lg text-text-primary appearance-none focus:outline-none focus:border-green/30 transition-colors cursor-pointer"
                    >
                        {LANGUAGES.map((lang) => (
                            <option key={lang.value} value={lang.value} className="bg-surface text-text-primary">
                                {lang.label}
                            </option>
                        ))}
                    </select>
                    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
                </div>
            </div>
        </div>
    );
}

function TabModel({ config, providerConfig, apiKeyInput, apiKeyDirty, showApiKey, onChange, setProviderConfig, setApiKeyInput, setApiKeyDirty, setShowApiKey }: {
    config: AgentConfig;
    providerConfig: ProviderConfig;
    apiKeyInput: string;
    apiKeyDirty: boolean;
    showApiKey: boolean;
    onChange: (key: keyof AgentConfig, value: string | number) => void;
    setProviderConfig: React.Dispatch<React.SetStateAction<ProviderConfig>>;
    setApiKeyInput: (v: string) => void;
    setApiKeyDirty: (v: boolean) => void;
    setShowApiKey: (v: boolean | ((prev: boolean) => boolean)) => void;
}) {
    return (
        <div className="space-y-6">
            {/* Provider selector */}
            <div>
                <FieldLabel hint="Leave empty to use the server default.">Provider</FieldLabel>
                <div className="flex gap-2.5">
                    {(["openai", "anthropic", "custom"] as const).map((p) => (
                        <button
                            key={p}
                            type="button"
                            onClick={() => {
                                if (providerConfig.name === p) {
                                    setProviderConfig({ name: "", api_key: "", api_base: "" });
                                    setApiKeyInput("");
                                    setApiKeyDirty(true);
                                } else {
                                    setProviderConfig((prev) => ({ ...prev, name: p }));
                                }
                            }}
                            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all cursor-pointer ${
                                providerConfig.name === p
                                    ? "bg-green/15 border-green/30 text-green"
                                    : "bg-glass border-glass-border text-text-muted hover:bg-glass-hover"
                            }`}
                        >
                            {p === "openai" ? "OpenAI" : p === "anthropic" ? "Anthropic" : "Custom"}
                        </button>
                    ))}
                </div>
            </div>

            {/* API Key (shown when provider is selected) */}
            {providerConfig.name && (
                <>
                    <div>
                        <FieldLabel>API Key</FieldLabel>
                        <div className="relative">
                            <Input
                                type={showApiKey ? "text" : "password"}
                                value={apiKeyInput}
                                onChange={(e) => {
                                    setApiKeyInput(e.target.value);
                                    setApiKeyDirty(true);
                                }}
                                onFocus={() => {
                                    if (!apiKeyDirty && apiKeyInput.includes("•")) {
                                        setApiKeyInput("");
                                        setApiKeyDirty(true);
                                    }
                                }}
                                placeholder="sk-..."
                                className="pr-9"
                            />
                            <button
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                                onClick={() => setShowApiKey((v) => !v)}
                            >
                                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                        {!apiKeyDirty && apiKeyInput && (
                            <p className="text-xs text-text-muted mt-1.5">
                                Key is masked. Click the field to enter a new one.
                            </p>
                        )}
                    </div>

                    {providerConfig.name === "custom" && (
                        <div>
                            <FieldLabel hint="OpenAI-compatible endpoint">API Base URL</FieldLabel>
                            <Input
                                value={providerConfig.api_base || ""}
                                onChange={(e) => setProviderConfig((prev) => ({ ...prev, api_base: e.target.value }))}
                                placeholder="https://api.example.com/v1"
                            />
                        </div>
                    )}
                </>
            )}

            {/* Model */}
            <div>
                <FieldLabel hint="Format: provider/model-name (e.g. openai/gpt-4o-mini)">Model</FieldLabel>
                <Input
                    value={config.model || ""}
                    onChange={(e) => onChange("model", e.target.value)}
                    placeholder="anthropic/claude-sonnet-4-20250514"
                />
            </div>
        </div>
    );
}

function TabAdvanced({ config, onChange }: {
    config: AgentConfig;
    onChange: (key: keyof AgentConfig, value: string | number) => void;
}) {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <FieldLabel hint="0 = deterministic, 2 = creative">Temperature</FieldLabel>
                    <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={config.temperature ?? ""}
                        onChange={(e) => onChange("temperature", parseFloat(e.target.value))}
                        placeholder="0.1"
                    />
                </div>
                <div>
                    <FieldLabel hint="Max response length">Max Tokens</FieldLabel>
                    <Input
                        type="number"
                        step="1"
                        min="256"
                        value={config.max_tokens ?? ""}
                        onChange={(e) => onChange("max_tokens", parseInt(e.target.value, 10))}
                        placeholder="8192"
                    />
                </div>
            </div>

            <div>
                <FieldLabel hint="How many tools the agent can call in one turn">Max Tool Iterations</FieldLabel>
                <Input
                    type="number"
                    step="1"
                    min="1"
                    max="100"
                    value={config.max_tool_iterations ?? ""}
                    onChange={(e) => onChange("max_tool_iterations", parseInt(e.target.value, 10))}
                    placeholder="40"
                />
            </div>

            <div>
                <FieldLabel hint="Messages before auto-consolidation into long-term memory. Lower = saves more often.">
                    Memory Window
                </FieldLabel>
                <Input
                    type="number"
                    step="1"
                    min="5"
                    max="200"
                    value={config.memory_window ?? ""}
                    onChange={(e) => onChange("memory_window", parseInt(e.target.value, 10))}
                    placeholder="20"
                />
            </div>
        </div>
    );
}

export function SettingsPanel() {
    const { settingsOpen, setPanelState } = useStore();
    const [tab, setTab] = useState<Tab>("general");
    const [config, setConfig] = useState<AgentConfig>({});
    const [providerConfig, setProviderConfig] = useState<ProviderConfig>({ name: "", api_key: "", api_base: "" });
    const [showApiKey, setShowApiKey] = useState(false);
    const [apiKeyInput, setApiKeyInput] = useState("");
    const [apiKeyDirty, setApiKeyDirty] = useState(false);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const loadConfig = async () => {
        setLoading(true);
        try {
            const [res, provRes] = await Promise.all([getConfig(), getProviderConfig()]);
            setConfig(res || {});
            const prov = provRes || { name: "", api_key: "", api_base: "" };
            setProviderConfig(prov);
            setApiKeyInput(prov.api_key || "");
            setShowApiKey(false);
            setApiKeyDirty(false);
        } catch (e) {
            toast("error", `Failed to load settings: ${(e as Error).message}`);
        }
        setLoading(false);
    };

    useEffect(() => {
        if (settingsOpen) {
            loadConfig();
            setSaved(false);
        }
    }, [settingsOpen]);

    const handleChange = (key: keyof AgentConfig, value: string | number) => {
        setConfig((prev) => ({ ...prev, [key]: value }));
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await updateConfig(config);
            const provPayload = { ...providerConfig };
            if (apiKeyDirty) {
                provPayload.api_key = apiKeyInput;
            }
            await updateProviderConfig(provPayload);
            setSaved(true);
            toast("success", "Settings saved");
            setApiKeyDirty(false);
            setTimeout(() => setSaved(false), 3000);
        } catch (e) {
            toast("error", `Failed to save: ${(e as Error).message}`);
        }
        setSaving(false);
    };

    return (
        <PanelWrapper
            open={settingsOpen}
            onClose={() => setPanelState("settings", false)}
            title="Settings"
            icon={Settings}
        >
            <form onSubmit={handleSave} className="flex-1 overflow-y-auto flex flex-col">
                {loading ? (
                    <div className="flex items-center justify-center p-12 flex-1">
                        <div className="w-6 h-6 border-2 border-green/30 border-t-green rounded-full animate-spin" />
                    </div>
                ) : (
                    <>
                        {/* Tab bar */}
                        <div className="flex border-b border-white/[0.06] bg-white/[0.01] px-3 pt-1.5 gap-1 shrink-0">
                            {TABS.map(({ id, label, icon: Icon }) => (
                                <button
                                    key={id}
                                    type="button"
                                    onClick={() => setTab(id)}
                                    className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors cursor-pointer relative ${
                                        tab === id
                                            ? "text-green bg-white/[0.04]"
                                            : "text-text-muted hover:text-text-secondary hover:bg-white/[0.02]"
                                    }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {label}
                                    {tab === id && (
                                        <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-green rounded-t-full" />
                                    )}
                                </button>
                            ))}
                        </div>

                        {/* Tab content */}
                        <div className="p-5 flex-1 overflow-y-auto">
                            {tab === "general" && (
                                <TabGeneral config={config} onChange={handleChange} />
                            )}
                            {tab === "model" && (
                                <TabModel
                                    config={config}
                                    providerConfig={providerConfig}
                                    apiKeyInput={apiKeyInput}
                                    apiKeyDirty={apiKeyDirty}
                                    showApiKey={showApiKey}
                                    onChange={handleChange}
                                    setProviderConfig={setProviderConfig}
                                    setApiKeyInput={setApiKeyInput}
                                    setApiKeyDirty={setApiKeyDirty}
                                    setShowApiKey={setShowApiKey}
                                />
                            )}
                            {tab === "advanced" && (
                                <TabAdvanced config={config} onChange={handleChange} />
                            )}
                        </div>
                    </>
                )}

                {/* Footer */}
                <div className="border-t border-white/[0.06] px-5 py-4 flex items-center justify-end gap-3 bg-white/[0.01] shrink-0">
                    {saved && (
                        <span className="flex items-center gap-1 text-xs text-green font-medium">
                            <Check className="w-3.5 h-3.5" />
                            Saved
                        </span>
                    )}
                    <Button type="submit" disabled={loading || saving} className="px-5">
                        {saving ? (
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        ) : (
                            <Save className="w-4 h-4 mr-2" />
                        )}
                        Save Settings
                    </Button>
                </div>
            </form>
        </PanelWrapper>
    );
}
