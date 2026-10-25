"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, KeyRound, LayoutDashboard, MessageSquare } from "lucide-react";

import { cn } from "@/lib/utils";

const tabs = [
  { suffix: "", label: "Overview", icon: LayoutDashboard },
  { suffix: "/documents", label: "Documents", icon: FileText },
  { suffix: "/api-keys", label: "API keys", icon: KeyRound },
  { suffix: "/playground", label: "Playground", icon: MessageSquare },
];

export function AgentTabs({ agentId }: { agentId: string }) {
  const pathname = usePathname();
  const base = `/dashboard/agents/${agentId}`;
  return (
    <nav className="mb-7 flex gap-1 overflow-x-auto rounded-xl border bg-white p-1.5 shadow-sm">
      {tabs.map(({ suffix, label, icon: Icon }) => {
        const href = `${base}${suffix}`;
        const active = suffix ? pathname.startsWith(href) : pathname === base;
        return (
          <Link key={label} href={href} className={cn(
            "focus-ring inline-flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition",
            active ? "bg-slate-950 text-white shadow-sm" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900",
          )}>
            <Icon className="size-4" /> {label}
          </Link>
        );
      })}
    </nav>
  );
}
