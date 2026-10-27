# Deploy AutoRAG on Render

The root `render.yaml` creates the recommended production topology: one API web
service, one Temporal background worker, Render Postgres, and Render Key Value.
`render.free.yaml` is the fallback topology that runs the worker inside the single
API process.

## 1. Prepare the external services

### Qdrant Cloud

1. Create a cluster and collection credentials in Qdrant Cloud.
2. Copy the HTTPS cluster URL into `QDRANT_URL` (for example,
   `https://cluster-id.region.cloud.qdrant.io:6333`).
3. Copy the database API key into `QDRANT_API_KEY`.
4. Keep `QDRANT_COLLECTION_NAME=autorag_chunks`. The ingestion code creates the
   collection when first needed.

### Temporal Cloud

Set `TEMPORAL_ADDRESS` to the gRPC endpoint including port `7233`, and set
`TEMPORAL_NAMESPACE` to the complete namespace ID shown by Temporal Cloud.

Choose exactly one authentication method:

- API key (recommended): set `TEMPORAL_API_KEY` and leave both mTLS variables empty.
- mTLS: leave `TEMPORAL_API_KEY` empty and set both `TEMPORAL_MTLS_CERT` and
  `TEMPORAL_MTLS_PRIVATE_KEY`. Each value can be pasted as PEM text, PEM text with
  literal `\n` separators, or base64-encoded PEM.

The API and worker must use the same address, namespace, authentication, and
`TEMPORAL_TASK_QUEUE`.

### AWS S3

1. Create a private S3 bucket in the desired AWS region.
2. Create an IAM user or role with `s3:PutObject`, `s3:GetObject`, and
   `s3:DeleteObject` on `arn:aws:s3:::YOUR_BUCKET/*`.
3. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `S3_BUCKET`.
4. Do not set `S3_ENDPOINT_URL` or `S3_PUBLIC_ENDPOINT_URL` for AWS S3; those are
   only needed for S3-compatible services such as local MinIO.

## 2. Deploy the Blueprint

1. Commit and push `render.yaml`, `backend/Dockerfile`, and the backend changes.
2. In Render, select **New > Blueprint** and connect the Git repository.
3. Leave the Blueprint path as `render.yaml`.
4. Review the four resources and click **Deploy Blueprint**.
5. Confirm the linked branch is `main`. The Blueprint uses
   `autoDeployTrigger: checksPass`, so later commits deploy only after GitHub Actions
   succeeds.
6. Render prompts once for every `sync: false` value. Required values are:
   `JWT_SECRET`, `CORS_ORIGINS`, `WIDGET_POLICY_TOKEN`, Qdrant, Temporal, AWS S3,
   `GEMINI_API_KEY`, and the answer-provider key used by each agent (for example
   `XAI_API_KEY`).
7. Leave unused provider and observability secrets blank. If reranking is disabled,
   `COHERE_API_KEY` can be blank.
8. Use a random value of at least 32 characters for `JWT_SECRET` and a separate
   long random value for `METRICS_TOKEN`.
9. Make sure the API and worker receive identical Qdrant, Temporal, AWS, Gemini,
   and JWT values. Blueprint secret values are entered separately for each service.
10. Wait for the API logs to show `Applying database migrations...` followed by
   Gunicorn startup. Wait for the worker logs to show `temporal_worker_started`.
11. Open `https://YOUR-API.onrender.com/health`; it should return HTTP 200.

Optionally validate either file first with Render CLI 2.7 or newer:

```bash
render blueprints validate render.yaml
render blueprints validate render.free.yaml
```

## 3. Connect the frontend

1. Set `CORS_ORIGINS` on the API to the exact Vercel production origin, without a
   trailing slash, such as `https://autorag.vercel.app`.
2. Set `CORS_ORIGIN_REGEX` to a project-scoped expression for Vercel previews, such
   as `^https://autorag(?:-[a-z0-9-]+)*\\.vercel\\.app$`. Do not allow every
   `*.vercel.app` deployment.
3. In Vercel, set `NEXT_PUBLIC_API_URL=https://YOUR-API.onrender.com` and redeploy.
4. Set the same long random `WIDGET_POLICY_TOKEN` on the Render API and Vercel.
5. If using the widget, also set `NEXT_PUBLIC_APP_URL` to the Vercel frontend URL
   and add each embedding site origin to the agent's `allowed_origins`.

## 4. Post-deployment checks

1. Sign up and create an agent.
2. Upload a small document and confirm its status changes from `pending` to
   `ready`.
3. Ask a grounded question in the playground and verify tokens and citations.
4. Check Qdrant for points containing the correct `tenant_id` and `agent_id`.
5. Check the Temporal Cloud UI for a completed `document-ingestion` workflow.
6. Check protected metrics with
   `curl -H "Authorization: Bearer $METRICS_TOKEN" https://YOUR-API.onrender.com/metrics`.

## Free-tier fallback

Create a separate Blueprint and set its Blueprint path to `render.free.yaml`. It
does not create a background worker. Instead it sets:

```text
RUN_TEMPORAL_WORKER_IN_PROCESS=true
WEB_CONCURRENCY=1
```

This is suitable for demos, not reliable production ingestion. A free web service
can sleep when idle, which also stops its in-process Temporal worker. A document
workflow will not progress until Render wakes the API again. Never set more than one
Gunicorn worker in this mode, because every web process would start another Temporal
worker and increase memory use.
