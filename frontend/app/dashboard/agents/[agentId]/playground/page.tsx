import { ChatPlayground } from "@/components/dashboard/chat-playground";
import { PageHeader } from "@/components/dashboard/page-header";

export default function PlaygroundPage({ params }: { params: { agentId: string } }) {
  return <><PageHeader title="Playground" description="Test retrieval, conversation memory, answer streaming, and source citations." /><ChatPlayground agentId={params.agentId} /></>;
}
