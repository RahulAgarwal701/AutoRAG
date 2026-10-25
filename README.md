# AutoRAG

AutoRAG is a multi-tenant platform for building document-grounded AI agents with an authenticated REST API and an embeddable chat widget.

## Repository layout

- `backend/` — FastAPI, SQLAlchemy, Alembic, Temporal workflows, and LangGraph agents
- `frontend/` — Next.js 14 App Router application
- `infra/` — local Docker Compose infrastructure

## Quick start

1. Copy the example environment file: `cp .env.example .env`
2. Create a free Gemini API key at <https://aistudio.google.com/apikey> and set
   `GEMINI_API_KEY` in `.env` (document ingestion requires it).
3. Start the complete local stack: `make dev`
4. Open the frontend at <http://localhost:3000>
5. Check the API at <http://localhost:8000/health>
6. Open Temporal UI at <http://localhost:8080>
7. Open MinIO Console at <http://localhost:9001>
8. Open Qdrant Dashboard at <http://localhost:6333/dashboard>

Run backend tests with `make test` and database migrations with `make migrate`.

Authentication endpoints are under `/api/v1/auth`. Tenant-protected agent, document, and API-key endpoints require `Authorization: Bearer <access_token>`. A newly issued API key is returned only by its creation request; subsequent responses expose only its prefix.

Document uploads use multipart form data at `POST /api/v1/agents/{agent_id}/documents`. Supported formats are PDF, DOCX, TXT, Markdown, and HTML. Uploaded objects are stored below a tenant/agent prefix, and successful uploads enqueue the `document-ingestion` Temporal workflow. Original files are viewed through short-lived URLs from `GET /api/v1/agents/{agent_id}/documents/{document_id}/view-url`.

The ingestion worker runs separately by default with `python -m app.workflows.worker`.
For a single free-tier service, set `RUN_TEMPORAL_WORKER_IN_PROCESS=true` and do not run
the separate worker container. Agents can select `recursive` or `semantic` chunking with
a 500–800 token target and 10–15% overlap. Set `SPARSE_EMBEDDING_PROVIDER=splade` to use
SPLADE instead of the default local BM25 sparse vectors.

Test retrieval from the terminal after an agent has at least one ready document:

```bash
cd backend
uv run python -m app.scripts.retrieve \
  --tenant-id <user-uuid> \
  --agent-id <agent-uuid> \
  --query "What does the document say about refunds?"
```

Hybrid retrieval fuses dense and sparse candidates with reciprocal rank fusion and
always filters by tenant and agent. If an agent has `use_reranker=true`, set
`COHERE_API_KEY`; otherwise Cohere is not called.

Document-grounded chat streams Server-Sent Events from
`POST /api/v1/agents/{agent_id}/chat/stream`. Gemini is the default provider with
the free-tier `gemini-2.5-flash-lite` model, using the same `GEMINI_API_KEY` as
retrieval. OpenAI and Claude remain optional provider choices. Send JSON containing
`message` and an optional `session_id`. The stream begins with a `session` event,
emits `token` events, and ends with a structured `citations` event. Set Langfuse
credentials to trace runs; tracing is disabled locally when they are absent.

xAI Grok is also available as `llm_provider: "grok"`. Set `XAI_API_KEY`, then
create a new Grok agent or switch an existing agent with
`PATCH /api/v1/agents/{agent_id}/llm`. The default Grok model is `grok-4.7`, and
`XAI_BASE_URL` defaults to the official `https://api.x.ai/v1` endpoint.

Per-agent tools are configured in the `tools` array. Calculator prompts begin with
`calculate`, web-search prompts with `search web for`, and custom webhook prompts
with `use <tool-name>:`. Webhooks must use HTTPS and their hosts must be listed in
`TOOL_WEBHOOK_ALLOWED_HOSTS`.

## Public API and widget authentication

Server integrations call `POST /v1/agents/{agent_id}/chat` with the one-time-issued
agent key in `Authorization: Bearer ark_live_...`. Set `stream: true` for SSE or
`stream: false` for a JSON response. Both modes accept `session_id` to continue a
conversation. The OpenAPI schema and examples are available at
<http://localhost:8000/docs> and <http://localhost:8000/openapi.json>.

Browser widgets never receive the agent API key. Configure `allowed_origins`, then:

1. Read `GET /v1/agents/{agent_id}/public-config` from an allowed origin.
2. Request `POST /v1/agents/{agent_id}/widget/session` from that origin.
3. Use its short-lived Bearer token with the public chat endpoint.

The widget token is bound to the requesting origin and agent. Dynamic CORS rejects
other browser origins. Redis applies atomic sliding-window limits per API key and IP;
limits and the widget-token lifetime are configurable in `.env`.

Example JSON chat request:

```bash
curl -X POST "http://localhost:8000/v1/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the invoice total?","stream":false}'
```

Update widget settings from the authenticated dashboard API with
`PATCH /api/v1/agents/{agent_id}/widget-config`, providing `greeting`, `theme`, and
`allowed_origins`.

For host-based development, install [uv](https://docs.astral.sh/uv/) and Node.js 20+, then run `uv sync` in `backend/` and `npm install` in `frontend/`.

