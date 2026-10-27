import { proxyAuthenticatedRequest } from "@/lib/server/backend";

type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: Context): Promise<Response> {
  const { path: segments } = await context.params;
  const path = `/${segments.join("/")}`;
  if (!path.startsWith("/api/v1/")) {
    return Response.json({ detail: "Unsupported API path" }, { status: 404 });
  }
  const requestUrl = new URL(request.url);
  return proxyAuthenticatedRequest(request, `${path}${requestUrl.search}`);
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
