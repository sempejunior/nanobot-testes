import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PanelWrapper } from "@/components/ui/panel-wrapper";
import {
  listCronJobs,
  addCronJob,
  deleteCronJob,
} from "@/lib/api";
import type { CronJob } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Clock, Plus, Trash2 } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CronPanel({ open, onClose }: Props) {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [kind, setKind] = useState<"every" | "cron">("every");
  const [everySeconds, setEverySeconds] = useState("3600");
  const [cronExpr, setCronExpr] = useState("0 9 * * *");

  const loadJobs = async () => {
    setLoading(true);
    try {
      setJobs(await listCronJobs());
    } catch (e) {
      toast("error", `Failed to load jobs: ${(e as Error).message}`);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (open) loadJobs();
  }, [open]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !message.trim()) return;
    try {
      await addCronJob({
        name: name.trim(),
        message: message.trim(),
        kind,
        ...(kind === "every"
          ? { every_seconds: parseInt(everySeconds) || 3600 }
          : { expr: cronExpr }),
      });
      toast("success", `Task "${name.trim()}" created`);
      setName("");
      setMessage("");
      setShowForm(false);
      loadJobs();
    } catch (e) {
      toast("error", `Failed to add task: ${(e as Error).message}`);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteCronJob(id);
      toast("success", "Task deleted");
      loadJobs();
    } catch (e) {
      toast("error", `Failed to delete: ${(e as Error).message}`);
    }
  };

  return (
    <PanelWrapper open={open} onClose={onClose} title="Scheduled Tasks" icon={Clock}>
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-green/30 border-t-green rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 && !showForm ? (
          <div className="flex flex-col items-center justify-center py-12 text-text-muted">
            <Clock className="w-10 h-10 mb-3 opacity-20" />
            <p className="text-sm">No scheduled tasks</p>
            <p className="text-xs mt-1 opacity-60">Create one to automate the agent</p>
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 hover:bg-white/[0.05] transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-text-primary truncate">
                    {job.name}
                  </div>
                  <div className="text-xs text-text-muted mt-1">
                    {job.schedule_kind === "cron"
                      ? `Cron: ${job.schedule_expr}`
                      : job.schedule_expr}
                  </div>
                  <div className="text-sm text-text-secondary mt-1.5 line-clamp-2">
                    {job.message}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(job.id)}
                  className="p-1.5 rounded hover:bg-red-muted hover:text-red text-text-muted transition-colors cursor-pointer shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2.5">
                <span
                  className={`inline-block text-xs px-2.5 py-1 rounded-full ${
                    job.enabled
                      ? "bg-green-muted text-green"
                      : "bg-yellow-muted text-yellow"
                  }`}
                >
                  {job.enabled ? "Active" : "Disabled"}
                </span>
              </div>
            </div>
          ))
        )}

        {/* Add form */}
        {showForm && (
          <form
            onSubmit={handleAdd}
            className="rounded-lg border border-green/20 bg-white/[0.03] p-5 space-y-4"
          >
            <div>
              <label className="block text-sm text-text-secondary mb-1.5">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Task name"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1.5">Message</label>
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="What should the bot do?"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1.5">Schedule</label>
              <div className="flex rounded-lg bg-white/[0.04] border border-white/[0.06] p-1 mb-3">
                <button
                  type="button"
                  onClick={() => setKind("every")}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 cursor-pointer ${
                    kind === "every"
                      ? "bg-green text-black shadow-[0_0_12px_rgba(17,199,111,0.3)]"
                      : "text-text-secondary"
                  }`}
                >
                  Interval
                </button>
                <button
                  type="button"
                  onClick={() => setKind("cron")}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 cursor-pointer ${
                    kind === "cron"
                      ? "bg-green text-black shadow-[0_0_12px_rgba(17,199,111,0.3)]"
                      : "text-text-secondary"
                  }`}
                >
                  Cron
                </button>
              </div>
              {kind === "every" ? (
                <Input
                  value={everySeconds}
                  onChange={(e) => setEverySeconds(e.target.value)}
                  placeholder="Seconds"
                  type="number"
                />
              ) : (
                <Input
                  value={cronExpr}
                  onChange={(e) => setCronExpr(e.target.value)}
                  placeholder="0 9 * * *"
                />
              )}
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="sm" className="flex-1">
                Add Task
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        )}
      </div>

      {/* Footer */}
      {!showForm && (
        <div className="p-5 border-t border-white/[0.06]">
          <Button
            className="w-full"
            variant="outline"
            onClick={() => setShowForm(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Scheduled Task
          </Button>
        </div>
      )}
    </PanelWrapper>
  );
}
