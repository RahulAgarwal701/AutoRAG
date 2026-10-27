import { AgentOverview } from "@/components/dashboard/agent-overview";

export default async function AgentPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  return <AgentOverview agentId={agentId} />;
}
