"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Button = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger"; size?: "sm" | "md" }>(function Button({ className, variant = "outline", size = "md", ...p }, ref) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-colors disabled:opacity-50",
        size === "sm" ? "h-8 px-3.5 text-xs" : "h-10 px-5 text-sm",
        variant === "primary" && "bg-indigo text-paper hover:opacity-90",
        variant === "outline" && "border border-line bg-paper hover:bg-paper-2",
        variant === "ghost" && "hover:bg-paper-2",
        variant === "danger" && "border border-rose/40 text-rose hover:bg-rose-soft",
        className,
      )}
      {...p}
    />
  );
});

export const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("rounded-2xl border border-line bg-paper", className)} {...p} />;

export function Chip({ tone = "neutral", className, ...p }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "teal" | "indigo" | "sand" | "rose" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        { neutral: "bg-paper-2 text-muted", teal: "bg-teal-soft text-teal", indigo: "bg-indigo-soft text-indigo", sand: "bg-sand-soft text-[color-mix(in_oklab,var(--sand)_70%,var(--ink))]", rose: "bg-rose-soft text-rose" }[tone],
        className,
      )}
      {...p}
    />
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden className={cn("skeleton h-4", className)} />;

export function Empty({ icon, title, children, action }: { icon: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="paper-texture flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line px-6 py-14 text-center">
      <div className="grid size-11 place-items-center rounded-full bg-indigo-soft text-indigo">{icon}</div>
      <h3 className="font-serif text-lg">{title}</h3>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-rose/30 bg-rose-soft px-4 py-3 text-sm">
      <span className="text-rose">{error instanceof Error ? error.message : String(error)}</span>
      {onRetry && <Button size="sm" onClick={onRetry}>Retry</Button>}
    </div>
  );
}
