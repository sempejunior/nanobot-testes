import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "ghost" | "outline" | "danger";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantStyles: Record<Variant, string> = {
  default: "bg-green text-black font-semibold hover:bg-green-hover shadow-[0_0_20px_rgba(17,199,111,0.25)]",
  ghost: "bg-transparent hover:bg-white/[0.05] text-text-secondary hover:text-text-primary",
  outline: "border border-white/[0.08] bg-white/[0.03] backdrop-blur-sm hover:bg-white/[0.06] hover:border-white/[0.12] text-text-primary",
  danger: "bg-red-muted text-red hover:bg-red/20",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-8 px-3 text-sm rounded-md",
  md: "h-10 px-4 text-sm rounded-lg",
  lg: "h-12 px-6 text-base rounded-lg",
  icon: "h-9 w-9 rounded-lg flex items-center justify-center",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-200",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green/50",
          "disabled:opacity-50 disabled:pointer-events-none",
          "cursor-pointer",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        disabled={disabled}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
