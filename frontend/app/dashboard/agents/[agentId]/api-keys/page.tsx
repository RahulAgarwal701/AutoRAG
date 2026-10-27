import { ApiKeyManager } from "@/components/dashboard/api-key-manager";

export default async function ApiKeysPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  return <ApiKeyManager agentId={agentId} />;
}
