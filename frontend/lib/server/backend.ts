import { cookies } from "next/headers";

export const ACCESS_COOKIE = "autorag_access";
export const REFRESH_COOKIE = "autorag_refresh";

function backendUrl(path: string): string {
  const base =
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  };
}

export async function storeTokens(accessToken: string, refreshToken: string): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, accessToken, cookieOptions(15 * 60));
  jar.set(REFRESH_COOKIE, refreshToken, cookieOptions(7 * 24 * 60 * 60));
}

export async function clearTokens(): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, "", cookieOptions(0));
  jar.set(REFRESH_COOKIE, "", cookieOptions(0));
}

export async function authenticate(
  action: "login" | "signup",
  credentials: unknown,
): Promise<Response> {
  const response = await fetch(backendUrl(`/api/v1/auth/${action}`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });
  if (!response.ok) return response;
  const payload = await response.json();
  await storeTokens(payload.access_token, payload.refresh_token);
  return Response.json({ user: payload.user }, { status: response.status });
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;
  const response = await fetch(backendUrl("/api/v1/auth/refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) {
    await clearTokens();
    return null;
  }
  const payload = await response.json();
  await storeTokens(payload.access_token, payload.refresh_token);
  return payload.access_token;
}

function forwardedHeaders(request: Request, token: string): Headers {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  headers.set("authorization", `Bearer ${token}`);
  return headers;
}

export async function proxyAuthenticatedRequest(
  request: Request,
  backendPath: string,
): Promise<Response> {
  let token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const send = (accessToken: string) =>
    fetch(backendUrl(backendPath), {
      method: request.method,
      headers: forwardedHeaders(request, accessToken),
      body,
      cache: "no-store",
      redirect: "manual",
    });

  let response = await send(token);
  if (response.status === 401) {
    const refreshedToken = await refreshAccessToken();
    if (!refreshedToken) {
      return Response.json({ detail: "Session expired" }, { status: 401 });
    }
    token = refreshedToken;
    response = await send(refreshedToken);
  }

  const headers = new Headers(response.headers);
  headers.delete("content-length");
  headers.delete("content-encoding");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
