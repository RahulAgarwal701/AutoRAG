import type { ReactNode } from "react";
import { Bot } from "lucide-react";

import { Card } from "@/components/ui/card";

export function EmptyState({ action }: { action?: ReactNode }) {
  return (
    <Card className="flex min-h-96 flex-col items-center justify-center px-6 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-violet-50 text-violet-600">
        <Bot className="size-7" />
      </span>
      <h2 className="mt-5 text-xl font-semibold">Build your first agent</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
        Upload your knowledge, tune how your agent responds, and deploy it through an API or widget.
      </p>
      <div className="mt-6">{action}</div>
    </Card>
  );
}
