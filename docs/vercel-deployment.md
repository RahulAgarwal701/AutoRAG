# Deploy the AutoRAG frontend on Vercel

## Project settings

1. Import the AutoRAG Git repository in Vercel.
2. Set **Root Directory** to `frontend` (the dashboard may display it as
   `./frontend`).
3. Set the Git **Production Branch** to `main`; Vercel will automatically create a
   production deployment for pushes and merges to that branch.
4. Keep **Framework Preset** as Next.js.
5. Use the detected commands: `npm install` and `npm run build`.
6. Do not set a custom Output Directory.

## Environment variables

Configure these for Production, Preview, and Development unless stated otherwise:

| Variable | Visibility | Value |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Browser-visible | `https://YOUR-API.onrender.com` |
| `NEXT_PUBLIC_APP_URL` | Browser-visible | Production Vercel origin, such as `https://autorag.vercel.app` |
| `API_INTERNAL_URL` | Server-only | `https://YOUR-API.onrender.com` |
| `WIDGET_POLICY_TOKEN` | Secret, server-only | Same long random value as the Render API |

Never prefix `WIDGET_POLICY_TOKEN` with `NEXT_PUBLIC_`.

On the Render API set:

```env
CORS_ORIGINS=https://autorag.vercel.app
CORS_ORIGIN_REGEX=^https://autorag(?:-[a-z0-9-]+)*\.vercel\.app$
WIDGET_POLICY_TOKEN=<same-value-as-vercel>
```

Replace `autorag` with the actual Vercel project slug. The regex deliberately
matches only that project's preview domains, not every application hosted on
Vercel. Redeploy the Render API after changing environment variables.

## Framing and loader security

- Dashboard, login, signup, and other normal pages return both
  `Content-Security-Policy: frame-ancestors 'none'` and `X-Frame-Options: DENY`.
- `/embed/{agentId}` asks the Render API for that agent's `allowed_origins` using
  the server-only policy token. Its CSP lists only valid stored HTTP(S) origins.
- If the policy lookup fails, the token is missing, the agent does not exist, or
  there are no valid allowed origins, framing fails closed with
  `frame-ancestors 'none'`.
- `/widget.js` is public and cross-origin loadable. Browsers cache it for five
  minutes while Vercel's CDN caches it for one day and can serve stale content
  during revalidation for seven days.

## End-to-end smoke test

Define convenient shell values first:

```bash
export APP_URL="https://autorag.vercel.app"
export API_URL="https://YOUR-API.onrender.com"
export TEST_ORIGIN="http://localhost:4173"
```

### 1. Health and frontend

```bash
curl -i "$API_URL/health"
curl -I "$APP_URL/login"
curl -I "$APP_URL/widget.js"
```

Confirm `/health` is `200`, normal pages contain `X-Frame-Options: DENY`, and
`widget.js` contains `Access-Control-Allow-Origin: *`,
`Cross-Origin-Resource-Policy: cross-origin`, and the expected cache headers.

### 2. Sign up and create an agent

1. Open `$APP_URL/signup` and create a new account.
2. Create an agent in the dashboard.
3. Select the configured answer provider. If Cohere is not configured, leave
   **Cohere reranker** disabled.
4. In widget settings, save `$TEST_ORIGIN` as an allowed origin.

### 3. Upload and ingest a document

1. Upload a small PDF, TXT, Markdown, DOCX, or HTML document.
2. Confirm its status moves through `pending`/`processing` to `ready`.
3. In Temporal Cloud, confirm the `document-ingestion` workflow completes.
4. In Qdrant Cloud, confirm the collection contains points for the document.

If the document remains pending, inspect the Render worker logs and verify its
Temporal, Qdrant, AWS, and Gemini variables match the API service.

### 4. Chat and citations

1. Open the agent Playground.
2. Ask a question whose answer appears clearly in the document.
3. Confirm the answer streams and contains citation markers such as `[1]`.
4. Confirm the Sources panel shows the correct document, snippet, and page when
   available.

### 5. Public API through curl

Generate an agent API key in the Deploy step and copy it immediately. Then run:

```bash
export AGENT_ID="<agent-uuid>"
export AGENT_API_KEY="ark_live_<copy-once-secret>"

curl -sS -X POST "$API_URL/v1/agents/$AGENT_ID/chat" \
  -H "Authorization: Bearer $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the main conclusion in the document?","stream":false}'
```

Confirm the JSON contains `session_id`, `answer`, `citations`, and `usage`.

### 6. Cross-origin widget

Copy `examples/widget-demo.html` outside the frontend deployment or create a page
containing:

```html
<script
  src="https://autorag.vercel.app/widget.js"
  data-agent-id="<agent-uuid>">
</script>
```

For the included local demo, replace its script URL and agent ID, then run from the
repository root:

```bash
python3 -m http.server 4173 --directory examples
```

Open `http://localhost:4173`, launch the widget, and send a grounded question.
Confirm streaming and citations work. Then remove `$TEST_ORIGIN` from the agent's
allowlist and reload: the session request or iframe must be rejected.

### 7. Direct header checks

```bash
curl -I "$APP_URL/dashboard"
curl -I "$APP_URL/embed/$AGENT_ID"
```

The dashboard must return `frame-ancestors 'none'` and `X-Frame-Options: DENY`.
The embed response must omit `X-Frame-Options` and its `frame-ancestors` directive
must list exactly the valid origins saved for that agent. Test successful framing
through the allowed external page as the final browser-level check.
