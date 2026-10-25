import { PageHeader } from "@/components/dashboard/page-header";
import { UsageDashboard } from "@/components/dashboard/usage-dashboard";

export default function UsagePage() {
  return <><PageHeader eyebrow="Workspace" title="Usage" description="A tenant-scoped view of agents, indexed knowledge, conversations, and credentials." /><UsageDashboard /></>;
}
