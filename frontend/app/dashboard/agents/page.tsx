import Link from "next/link";
import { Plus } from "lucide-react";

import { AgentsList } from "@/components/dashboard/agents-list";
import { PageHeader } from "@/components/dashboard/page-header";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Your agents"
        description="Build, test, and deploy assistants grounded in your own knowledge."
        action={<Button asChild><Link href="/dashboard/agents/new"><Plus className="mr-2 size-4" />Create agent</Link></Button>}
      />
      <AgentsList />
    </>
  );
}
