import { ApiKeyManager } from "@/components/dashboard/api-key-manager";

export default function ApiKeysPage({ params }: { params: { agentId: string } }) {
  return <ApiKeyManager agentId={params.agentId} />;
}
