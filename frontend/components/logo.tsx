import Link from "next/link";
import { Sparkles } from "lucide-react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="focus-ring inline-flex items-center gap-2.5 rounded-lg">
      <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/20">
        <Sparkles className="size-4.5" />
      </span>
      {!compact && <span className="text-lg font-bold tracking-tight">AutoRAG</span>}
    </Link>
  );
}
