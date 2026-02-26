import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-sm text-text-primary",
          "placeholder:text-text-muted",
          "focus:outline-none focus:ring-2 focus:ring-green/15 focus:border-green/40",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "transition-all duration-200 resize-none",
          className
        )}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";
