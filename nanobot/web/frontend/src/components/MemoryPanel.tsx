import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { PanelWrapper } from "@/components/ui/panel-wrapper";
import {
    getMemory,
    updateLongTermMemory,
    clearMemoryHistory,
    deleteMemoryHistoryEntry,
    searchMemory,
} from "@/lib/api";
import type { MemoryData, MemorySearchResult } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useStore } from "@/lib/store";
import {
    Brain,
    Trash2,
    Save,
    Search,
    X,
    BookOpen,
    Clock,
    Check,
} from "lucide-react";

export function MemoryPanel() {
    const { memoryOpen, setPanelState } = useStore();
    const [data, setData] = useState<MemoryData | null>(null);
    const [loading, setLoading] = useState(false);
    const [longTerm, setLongTerm] = useState("");
    const [dirty, setDirty] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Search
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<MemorySearchResult[] | null>(null);
    const [searching, setSearching] = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Delete confirmation
    const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
    const [confirmClearAll, setConfirmClearAll] = useState(false);

    const loadMemory = async () => {
        setLoading(true);
        try {
            const mem = await getMemory();
            setData(mem);
            setLongTerm(mem.long_term || "");
            setDirty(false);
        } catch (e) {
            toast("error", `Failed to load memory: ${(e as Error).message}`);
        }
        setLoading(false);
    };

    useEffect(() => {
        if (memoryOpen) {
            loadMemory();
            setSearchQuery("");
            setSearchResults(null);
            setConfirmDeleteId(null);
            setConfirmClearAll(false);
        }
    }, [memoryOpen]);

    const doSearch = useCallback(async (query: string) => {
        if (!query.trim()) {
            setSearchResults(null);
            setSearching(false);
            return;
        }
        setSearching(true);
        try {
            const res = await searchMemory(query.trim());
            setSearchResults(res.results);
        } catch {
            setSearchResults(null);
        }
        setSearching(false);
    }, []);

    const handleSearchChange = (value: string) => {
        setSearchQuery(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => doSearch(value), 300);
    };

    const handleSaveLongTerm = async () => {
        setSaving(true);
        try {
            await updateLongTermMemory(longTerm);
            setDirty(false);
            setSaved(true);
            toast("success", "Core memory saved");
            setTimeout(() => setSaved(false), 2000);
            loadMemory();
        } catch (e) {
            toast("error", `Failed to save: ${(e as Error).message}`);
        }
        setSaving(false);
    };

    const handleClearHistory = async () => {
        setConfirmClearAll(false);
        try {
            await clearMemoryHistory();
            toast("success", "History cleared");
            loadMemory();
        } catch (e) {
            toast("error", `Failed to clear history: ${(e as Error).message}`);
        }
    };

    const handleDeleteEntry = async (id: number) => {
        setConfirmDeleteId(null);
        try {
            await deleteMemoryHistoryEntry(id);
            toast("success", "Entry deleted");
            loadMemory();
            if (searchQuery.trim()) doSearch(searchQuery);
        } catch (e) {
            toast("error", `Failed to delete entry: ${(e as Error).message}`);
        }
    };

    const historyEntries = searchResults !== null ? searchResults : (data?.history ?? []);

    return (
        <PanelWrapper
            open={memoryOpen}
            onClose={() => setPanelState("memory", false)}
            title="Agent Memory"
            icon={Brain}
        >
            <div className="flex-1 overflow-y-auto">
                {loading && !data ? (
                    <div className="flex items-center justify-center p-12">
                        <div className="w-6 h-6 border-2 border-green/30 border-t-green rounded-full animate-spin" />
                    </div>
                ) : (
                    <>
                        {/* ── Core Memory ── */}
                        <div className="p-5 pb-0">
                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                                <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/[0.06] bg-white/[0.02]">
                                    <div className="flex items-center gap-2.5">
                                        <BookOpen className="w-4 h-4 text-green" />
                                        <span className="text-sm font-medium text-text-primary">Core Memory</span>
                                    </div>
                                    <span className="text-xs text-text-muted">Permanent rules & facts</span>
                                </div>
                                <div className="p-4">
                                    <textarea
                                        value={longTerm}
                                        onChange={(e) => {
                                            setLongTerm(e.target.value);
                                            setDirty(true);
                                            setSaved(false);
                                        }}
                                        placeholder="Enter permanent instructions or facts about the user here...&#10;&#10;Example:&#10;- User's name is Carlos&#10;- Prefers responses in Portuguese&#10;- Works at PicPay as a developer"
                                        className="w-full min-h-[140px] resize-none text-sm leading-relaxed bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none font-mono"
                                    />
                                </div>
                                <div className="flex items-center justify-end gap-2.5 px-4 pb-4">
                                    {saved && (
                                        <span className="flex items-center gap-1.5 text-xs text-green font-medium">
                                            <Check className="w-3.5 h-3.5" />
                                            Saved
                                        </span>
                                    )}
                                    <Button
                                        size="sm"
                                        onClick={handleSaveLongTerm}
                                        disabled={!dirty || saving}
                                    >
                                        {saving ? (
                                            <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1.5" />
                                        ) : (
                                            <Save className="w-3.5 h-3.5 mr-1.5" />
                                        )}
                                        Save
                                    </Button>
                                </div>
                            </div>
                        </div>

                        {/* ── Conversational History ── */}
                        <div className="p-5 pt-4">
                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                                <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/[0.06] bg-white/[0.02]">
                                    <div className="flex items-center gap-2.5">
                                        <Clock className="w-4 h-4 text-green" />
                                        <span className="text-sm font-medium text-text-primary">
                                            Conversational History
                                        </span>
                                        {historyEntries.length > 0 && (
                                            <span className="text-xs text-text-muted bg-white/[0.06] px-2 py-0.5 rounded-full">
                                                {historyEntries.length}
                                            </span>
                                        )}
                                    </div>

                                    {/* Clear All with confirmation */}
                                    {confirmClearAll ? (
                                        <div className="flex items-center gap-1.5">
                                            <button
                                                onClick={handleClearHistory}
                                                className="px-2.5 py-1 text-xs font-medium rounded bg-red/20 text-red hover:bg-red/30 transition-colors cursor-pointer"
                                            >
                                                Confirm
                                            </button>
                                            <button
                                                onClick={() => setConfirmClearAll(false)}
                                                className="px-2.5 py-1 text-xs font-medium rounded bg-white/[0.06] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => setConfirmClearAll(true)}
                                            className="text-xs text-text-muted hover:text-red transition-colors cursor-pointer"
                                        >
                                            Clear All
                                        </button>
                                    )}
                                </div>

                                {/* Search bar */}
                                <div className="px-4 pt-4">
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                                        <input
                                            value={searchQuery}
                                            onChange={(e) => handleSearchChange(e.target.value)}
                                            placeholder="Search history..."
                                            className="w-full h-10 pl-9 pr-9 text-sm bg-white/[0.03] border border-white/[0.06] rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-green/30 transition-colors"
                                        />
                                        {searchQuery && (
                                            <button
                                                onClick={() => {
                                                    setSearchQuery("");
                                                    setSearchResults(null);
                                                }}
                                                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-white/[0.06] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                                            >
                                                <X className="w-3.5 h-3.5" />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Entries list */}
                                <div className="p-4 space-y-2.5">
                                    {searching && (
                                        <div className="flex items-center justify-center py-8">
                                            <div className="w-5 h-5 border-2 border-green/30 border-t-green rounded-full animate-spin" />
                                        </div>
                                    )}

                                    {!searching && historyEntries.length === 0 && (
                                        <div className="flex flex-col items-center justify-center py-10 text-text-muted">
                                            <Brain className="w-10 h-10 mb-3 opacity-20" />
                                            <p className="text-sm">
                                                {searchQuery ? "No results found" : "No history recorded yet"}
                                            </p>
                                            {!searchQuery && (
                                                <p className="text-xs mt-1.5 opacity-60">
                                                    Memories are saved automatically as you chat
                                                </p>
                                            )}
                                        </div>
                                    )}

                                    {!searching && historyEntries.map((entry) => (
                                        <div
                                            key={entry.id}
                                            className="group relative rounded-lg border border-white/[0.04] bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.08] transition-all"
                                        >
                                            <div className="px-4 py-3">
                                                <p className="text-sm text-text-primary leading-relaxed break-words whitespace-pre-wrap pr-7">
                                                    {entry.content}
                                                </p>
                                                <div className="flex items-center justify-between mt-2.5">
                                                    <span className="text-xs text-text-muted font-mono">
                                                        {new Date(entry.created_at).toLocaleString()}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Delete button */}
                                            {confirmDeleteId === entry.id ? (
                                                <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
                                                    <button
                                                        onClick={() => handleDeleteEntry(entry.id)}
                                                        className="px-2.5 py-1 text-xs font-medium rounded bg-red/20 text-red hover:bg-red/30 transition-colors cursor-pointer"
                                                    >
                                                        Delete
                                                    </button>
                                                    <button
                                                        onClick={() => setConfirmDeleteId(null)}
                                                        className="px-2.5 py-1 text-xs font-medium rounded bg-white/[0.06] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => setConfirmDeleteId(entry.id)}
                                                    className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-red-muted hover:text-red text-text-muted transition-all cursor-pointer"
                                                    title="Delete entry"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </PanelWrapper>
    );
}
