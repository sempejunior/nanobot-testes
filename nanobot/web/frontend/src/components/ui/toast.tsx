import { useToastStore } from "@/lib/toast";
import type { Toast } from "@/lib/toast";
import { X, CheckCircle2, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

const icons = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

const styles = {
  success: "border-green/30 bg-green/10 text-green-light",
  error: "border-red/30 bg-red/10 text-red",
  info: "border-white/10 bg-white/[0.06] text-text-primary",
};

function ToastItem({ toast }: { toast: Toast }) {
  const { removeToast } = useToastStore();
  const Icon = icons[toast.type];
  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border backdrop-blur-xl shadow-lg animate-toast-in",
        styles[toast.type]
      )}
    >
      <Icon className="w-4 h-4 shrink-0" />
      <span className="text-sm flex-1">{toast.message}</span>
      <button
        onClick={() => removeToast(toast.id)}
        className="p-0.5 hover:opacity-70 cursor-pointer shrink-0"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const { toasts } = useToastStore();
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm pointer-events-auto">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
