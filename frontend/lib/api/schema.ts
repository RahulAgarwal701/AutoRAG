/* eslint-disable */
// Generated from openapi.json. Run: npm run generate:api
export interface components {
  schemas: {
    AgentCreate: { name: string; greeting?: string; theme?: { [key: string]: unknown; }; system_prompt: string; model?: string; llm_provider?: "gemini" | "grok" | "openai" | "claude"; temperature?: number; top_k?: number; use_reranker?: boolean; chunk_strategy?: "recursive" | "semantic"; chunk_size_tokens?: number; chunk_overlap_percent?: number; allowed_origins?: Array<string> ; tools?: Array<components["schemas"]["CalculatorToolConfig"] | components["schemas"]["WebSearchToolConfig"] | components["schemas"]["WebhookToolConfig"]> ; };
    AgentLLMUpdate: { llm_provider: "gemini" | "grok" | "openai" | "claude"; model?: string | null; };
    AgentRead: { name: string; greeting?: string; theme?: { [key: string]: unknown; }; system_prompt: string; model?: string; llm_provider?: "gemini" | "grok" | "openai" | "claude"; temperature?: number; top_k?: number; use_reranker?: boolean; chunk_strategy?: "recursive" | "semantic"; chunk_size_tokens?: number; chunk_overlap_percent?: number; allowed_origins?: Array<string> ; tools?: Array<components["schemas"]["CalculatorToolConfig"] | components["schemas"]["WebSearchToolConfig"] | components["schemas"]["WebhookToolConfig"]> ; id: string; created_at: string; };
    AgentUpdate: { name?: string | null; system_prompt?: string | null; model?: string | null; llm_provider?: "gemini" | "grok" | "openai" | "claude" | null; temperature?: number | null; top_k?: number | null; use_reranker?: boolean | null; tools?: Array<components["schemas"]["CalculatorToolConfig"] | components["schemas"]["WebSearchToolConfig"] | components["schemas"]["WebhookToolConfig"]>  | null; };
    AgentWidgetUpdate: { greeting: string; theme: { [key: string]: unknown; }; allowed_origins: Array<string> ; };
    ApiKeyCreated: { id: string; prefix: string; last_used_at: string | null; revoked: boolean; created_at: string; key: string; };
    ApiKeyRead: { id: string; prefix: string; last_used_at: string | null; revoked: boolean; created_at: string; };
    AuthResponse: { access_token: string; refresh_token: string; token_type?: string; user: components["schemas"]["UserRead"]; };
    Body_upload_document_api_v1_agents__agent_id__documents_post: { file: string; };
    CalculatorToolConfig: { type: "calculator"; enabled?: boolean; };
    ChatRequest: { message: string; session_id?: string | null; };
    Credentials: { email: string; password: string; };
    DocumentRead: { id: string; agent_id: string; filename: string; status: components["schemas"]["DocumentStatus"]; error: string | null; chunk_count: number; created_at: string; };
    DocumentStatus: "pending" | "processing" | "ready" | "failed";
    DocumentUsage: { total: number; pending: number; processing: number; ready: number; failed: number; indexed_chunks: number; };
    ErrorDetail: { code: string; message: string; request_id: string; };
    ErrorResponse: { error: components["schemas"]["ErrorDetail"]; };
    HTTPValidationError: { detail?: Array<components["schemas"]["ValidationError"]> ; };
    HealthResponse: { status: "ok"; };
    PresignedUrlResponse: { url: string; expires_in: number; };
    PublicAgentConfig: { name: string; greeting: string; theme: { [key: string]: unknown; }; };
    PublicChatRequest: { message: string; session_id?: string | null; stream?: boolean; };
    RefreshRequest: { refresh_token: string; };
    TokenPair: { access_token: string; refresh_token: string; token_type?: string; };
    UsageSummary: { agents: number; documents: components["schemas"]["DocumentUsage"]; chat_sessions: number; messages: number; active_api_keys: number; };
    UserRead: { id: string; email: string; created_at: string; };
    ValidationError: { loc: Array<string | number> ; msg: string; type: string; input?: unknown; ctx?: {  }; };
    WebSearchToolConfig: { type: "web_search"; enabled?: boolean; };
    WebhookToolConfig: { type: "webhook"; name: string; description: string; url: string; enabled?: boolean; };
    WidgetSessionResponse: { token: string; token_type?: string; expires_in: number; };
  };
}
