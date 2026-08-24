import * as React from "react";
import { cn } from "@/lib/utils";

interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Switch({ className, label, ...props }: SwitchProps) {
  return (
    <label className={cn("inline-flex items-center gap-2 cursor-pointer", className)}>
      <input
        type="checkbox"
        className={cn(
          "peer h-4 w-4 shrink-0 cursor-pointer appearance-none rounded-full border-2 border-input",
          "bg-transparent",
          "checked:bg-primary checked:border-primary",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "after:inline-block after:h-3 after:w-3 after:rounded-full after:bg-foreground",
          "peer-checked:after:translate-x-full",
          "transition-transform duration-200",
        )}
        {...props}
      />
      {label && <span className="text-sm font-medium">{label}</span>}
    </label>
  );
}