import { DocumentManager } from "@/components/dashboard/document-manager";

export default function DocumentsPage({ params }: { params: { agentId: string } }) {
  return <DocumentManager agentId={params.agentId} />;
}
