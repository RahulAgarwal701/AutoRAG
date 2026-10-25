"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Bot, LogOut, Menu, Plus, X } from "lucide-react";
import { useState } from "react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/dashboard/agents", label: "Agents", icon: Bot },
  { href: "/dashboard/usage", label: "Usage", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  const content = (
    <div className="flex h-full flex-col">
      <div className="flex h-20 items-center px-5"><Logo /></div>
      <div className="px-4">
        <Button asChild className="w-full justify-center shadow-lg shadow-violet-500/15">
          <Link href="/dashboard/agents/new" onClick={() => setOpen(false)}>
            <Plus className="mr-2 size-4" /> Create agent
          </Link>
        </Button>
      </div>
      <nav className="mt-7 space-y-1 px-3">
        {navigation.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={cn(
                "focus-ring flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                active
                  ? "bg-violet-50 text-violet-700"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-900",
              )}
            >
              <Icon className="size-4.5" /> {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t p-3">
        <button
          onClick={logout}
          className="focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
        >
          <LogOut className="size-4.5" /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-white/95 backdrop-blur lg:block">
        {content}
      </aside>
      <div className="fixed inset-x-0 top-0 z-30 flex h-16 items-center justify-between border-b bg-white/90 px-4 backdrop-blur lg:hidden">
        <Logo />
        <button className="focus-ring rounded-lg p-2" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu className="size-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-slate-950/40" onClick={() => setOpen(false)} aria-label="Close menu" />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-2xl">
            <button className="absolute right-4 top-5 rounded-lg p-2" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="size-5" />
            </button>
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
