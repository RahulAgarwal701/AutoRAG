import type { ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";

import { Logo } from "@/components/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
      <section className="relative hidden overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(124,58,237,.35),transparent_30%),radial-gradient(circle_at_80%_70%,rgba(14,165,233,.2),transparent_28%)]" />
        <div className="relative z-10 [&_a]:text-white"><Logo /></div>
        <div className="relative z-10 my-auto max-w-lg">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-violet-300">
            Document intelligence
          </p>
          <h1 className="mt-5 text-5xl font-semibold leading-tight tracking-tight">
            Answers you can trust, with sources you can verify.
          </h1>
          <div className="mt-10 space-y-4 text-slate-300">
            {["Grounded answers with citations", "Secure tenant-isolated APIs", "Deploy by API or widget"].map((item) => (
              <div key={item} className="flex items-center gap-3">
                <CheckCircle2 className="size-5 text-violet-400" /> {item}
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-sm text-slate-500">Built for teams that value accuracy.</p>
      </section>
      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-12 lg:hidden"><Logo /></div>
          {children}
        </div>
      </section>
    </main>
  );
}
