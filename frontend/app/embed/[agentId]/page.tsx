import { EmbedChat } from "@/components/widget/embed-chat";

export default async function EmbedPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  return <EmbedChat agentId={agentId} />;
}
