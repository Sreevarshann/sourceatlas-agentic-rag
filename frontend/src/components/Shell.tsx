"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, FlaskConical, Moon, Search, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Wordmark } from "./Logo";
import { useTheme } from "./theme";

const NAV = [
  { href: "/studio", label: "Research Studio", icon: Search },
  { href: "/library", label: "Knowledge Library", icon: BookOpen },
  { href: "/evaluation", label: "Evaluation", icon: FlaskConical },
];

function NavLinks({ path }: { path: string }) {
  return (
    <>
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = path.startsWith(href);
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition-colors", active ? "bg-indigo text-paper" : "text-muted hover:bg-paper-2 hover:text-ink")}>
            <Icon className="size-4" aria-hidden /> <span className="hidden sm:inline">{label}</span>
          </Link>
        );
      })}
    </>
  );
}

function ActiveNav() {
  return <NavLinks path={usePathname()} />;
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { theme, toggle } = useTheme();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center gap-6 px-4 py-3 sm:px-6">
          <Link href="/" aria-label="SourceAtlas home"><Wordmark /></Link>
          <nav aria-label="Primary" className="flex flex-1 items-center gap-1 overflow-x-auto">
            {/* usePathname is request data: keep it inside Suspense for Cache Components */}
            <Suspense fallback={<NavLinks path="" />}>
              <ActiveNav />
            </Suspense>
          </nav>
          <span className="hidden items-center gap-2 text-xs text-muted md:flex" title="API, pgvector and model status">
            <span className={cn("size-2 rounded-full", health.isError ? "bg-rose" : health.data?.status === "ok" ? "bg-teal" : "bg-sand")} />
            {health.isError ? "API offline" : health.data ? `pgvector ${health.data.pgvector} · ${health.data.embedding_model} · ${health.data.llm_provider}` : "connecting…"}
          </span>
          <button onClick={toggle} aria-label="Toggle theme" className="rounded-full p-2 text-muted hover:bg-paper-2">{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</button>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
