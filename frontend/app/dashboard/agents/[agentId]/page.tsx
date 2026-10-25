import { AgentOverview } from "@/components/dashboard/agent-overview";

export default function AgentPage({ params }: { params: { agentId: string } }) {
  return <AgentOverview agentId={params.agentId} />;
}
