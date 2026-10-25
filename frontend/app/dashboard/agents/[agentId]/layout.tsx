import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { AgentTabs } from "@/components/dashboard/agent-tabs";

export default function AgentLayout({ children, params }: { children: ReactNode; params: { agentId: string } }) {
  return (
    <>
      <Link href="/dashboard/agents" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" /> All agents
      </Link>
      <AgentTabs agentId={params.agentId} />
      {children}
    </>
  );
}
