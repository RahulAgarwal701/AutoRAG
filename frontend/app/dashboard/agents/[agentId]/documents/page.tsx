import { DocumentManager } from "@/components/dashboard/document-manager";

export default async function DocumentsPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  return <DocumentManager agentId={agentId} />;
}
