import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "h-10 w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 text-sm text-text-primary",
          "placeholder:text-text-muted",
          "focus:outline-none focus:ring-2 focus:ring-green/15 focus:border-green/40",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "transition-all duration-200",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
