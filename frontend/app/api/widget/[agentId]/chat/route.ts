import {
  forwardResponse,
  normalizeOrigin,
  publicBackendFetch,
} from "@/lib/server/widget";

type Context = { params: Promise<{ agentId: string }> };

export async function POST(request: Request, { params }: Context): Promise<Response> {
  const { agentId } = await params;
  const parentOrigin = normalizeOrigin(request.headers.get("x-autorag-parent-origin"));
  const authorization = request.headers.get("authorization");
  if (!parentOrigin || !authorization?.startsWith("Bearer ")) {
    return Response.json(
      { error: { code: "invalid_widget_session", message: "Widget session is missing" } },
      { status: 401 },
    );
  }
  const response = await publicBackendFetch(
    `/v1/agents/${encodeURIComponent(agentId)}/chat`,
    parentOrigin,
    {
      method: "POST",
      headers: {
        Authorization: authorization,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: await request.arrayBuffer(),
    },
  );
  const headers = new Headers({
    "Cache-Control": "no-cache, no-store",
    "X-Accel-Buffering": "no",
  });
  return forwardResponse(response, headers);
}
