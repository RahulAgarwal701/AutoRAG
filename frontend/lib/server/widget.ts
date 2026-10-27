function backendUrl(path: string): string {
  const base =
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

export function normalizeOrigin(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.pathname !== '/' || url.search || url.hash) {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

export async function publicBackendFetch(
  path: string,
  origin: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(backendUrl(path), {
    ...init,
    headers: {
      ...Object.fromEntries(new Headers(init?.headers).entries()),
      Origin: origin,
    },
    cache: "no-store",
  });
}

export function widgetCorsHeaders(origin: string): Headers {
  return new Headers({
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "600",
    "Cache-Control": "no-store",
    Vary: "Origin",
  });
}

export function forwardResponse(response: Response, headers = new Headers()): Response {
  headers.set("Content-Type", response.headers.get("content-type") ?? "application/json");
  const requestId = response.headers.get("x-request-id");
  if (requestId) headers.set("X-Request-ID", requestId);
  return new Response(response.body, { status: response.status, headers });
}
