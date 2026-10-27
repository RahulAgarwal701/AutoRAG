import { ChatPlayground } from "@/components/dashboard/chat-playground";
import { PageHeader } from "@/components/dashboard/page-header";

export default async function PlaygroundPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  return <><PageHeader title="Playground" description="Test retrieval, conversation memory, answer streaming, and source citations." /><ChatPlayground agentId={agentId} /></>;
}
