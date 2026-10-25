import type { components } from "@/lib/api/schema";

export type Agent = components["schemas"]["AgentRead"];
export type AgentCreate = components["schemas"]["AgentCreate"];
export type AgentUpdate = components["schemas"]["AgentUpdate"];
export type Document = components["schemas"]["DocumentRead"];
export type ApiKey = components["schemas"]["ApiKeyRead"];
export type ApiKeyCreated = components["schemas"]["ApiKeyCreated"];
export type UsageSummary = components["schemas"]["UsageSummary"];

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function errorMessage(payload: unknown): string {
  if (payload && typeof payload === "object") {
    const value = payload as { detail?: unknown; error?: { message?: unknown } };
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.error?.message === "string") return value.error.message;
  }
  return "Something went wrong";
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/backend/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (response.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login?reason=expired");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(errorMessage(payload), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listAgents: () => apiRequest<Agent[]>("/agents"),
  getAgent: (id: string) => apiRequest<Agent>(`/agents/${id}`),
  createAgent: (payload: AgentCreate) =>
    apiRequest<Agent>("/agents", { method: "POST", body: JSON.stringify(payload) }),
  updateAgent: (id: string, payload: AgentUpdate) =>
    apiRequest<Agent>(`/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  updateWidget: (
    id: string,
    payload: components["schemas"]["AgentWidgetUpdate"],
  ) =>
    apiRequest<Agent>(`/agents/${id}/widget-config`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  listDocuments: (agentId: string) =>
    apiRequest<Document[]>(`/agents/${agentId}/documents`),
  uploadDocument: (agentId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return apiRequest<Document>(`/agents/${agentId}/documents`, { method: "POST", body });
  },
  deleteDocument: (agentId: string, documentId: string) =>
    apiRequest<void>(`/agents/${agentId}/documents/${documentId}`, { method: "DELETE" }),
  documentUrl: (agentId: string, documentId: string) =>
    apiRequest<components["schemas"]["PresignedUrlResponse"]>(
      `/agents/${agentId}/documents/${documentId}/view-url`,
    ),
  listApiKeys: (agentId: string) =>
    apiRequest<ApiKey[]>(`/agents/${agentId}/api-keys`),
  createApiKey: (agentId: string) =>
    apiRequest<ApiKeyCreated>(`/agents/${agentId}/api-keys`, { method: "POST" }),
  revokeApiKey: (agentId: string, keyId: string) =>
    apiRequest<ApiKey>(`/agents/${agentId}/api-keys/${keyId}/revoke`, {
      method: "POST",
    }),
  usage: () => apiRequest<UsageSummary>("/usage"),
};
