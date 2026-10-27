import {
  forwardResponse,
  normalizeOrigin,
  publicBackendFetch,
  widgetCorsHeaders,
} from "@/lib/server/widget";

type Context = { params: Promise<{ agentId: string }> };

export async function OPTIONS(request: Request, { params }: Context): Promise<Response> {
  const { agentId } = await params;
  const origin = normalizeOrigin(request.headers.get("origin"));
  if (!origin) return Response.json({ error: { message: "Origin is required" } }, { status: 403 });
  const validation = await publicBackendFetch(
    `/v1/agents/${encodeURIComponent(agentId)}/public-config`,
    origin,
  );
  if (!validation.ok) return forwardResponse(validation);
  return new Response(null, { status: 204, headers: widgetCorsHeaders(origin) });
}

export async function POST(request: Request, { params }: Context): Promise<Response> {
  const { agentId } = await params;
  const origin = normalizeOrigin(request.headers.get("origin"));
  if (!origin) return Response.json({ error: { message: "Origin is required" } }, { status: 403 });
  const path = `/v1/agents/${encodeURIComponent(agentId)}`;
  const configResponse = await publicBackendFetch(`${path}/public-config`, origin);
  if (!configResponse.ok) {
    return forwardResponse(configResponse, widgetCorsHeaders(origin));
  }
  const sessionResponse = await publicBackendFetch(`${path}/widget/session`, origin, {
    method: "POST",
  });
  if (!sessionResponse.ok) {
    return forwardResponse(sessionResponse, widgetCorsHeaders(origin));
  }
  const [config, session] = await Promise.all([
    configResponse.json(),
    sessionResponse.json(),
  ]);
  return Response.json(
    { ...session, config },
    { status: 200, headers: widgetCorsHeaders(origin) },
  );
}
