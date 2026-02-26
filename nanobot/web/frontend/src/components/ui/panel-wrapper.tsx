import type { ReactNode } from "react";
import { Button } from "./button";
import { X } from "lucide-react";

interface PanelWrapperProps {
  open: boolean;
  onClose: () => void;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  maxWidth?: string;
  children: ReactNode;
}

export function PanelWrapper({
  open,
  onClose,
  title,
  icon: Icon,
  maxWidth = "max-w-xl",
  children,
}: PanelWrapperProps) {
  if (!open) return null;
  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 animate-fade-in"
        onClick={onClose}
      />
      <div
        className={`fixed right-0 top-0 h-full w-full ${maxWidth} backdrop-blur-2xl bg-background/80 border-l border-white/[0.06] z-50 flex flex-col animate-slide-in-right`}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] bg-white/[0.02]">
          <div className="flex items-center gap-2.5">
            <Icon className="w-5 h-5 text-green" />
            <h2 className="text-base font-semibold">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>
        {children}
      </div>
    </>
  );
}
