import { NextResponse, type NextRequest } from "next/server";

function backendUrl(path: string): string {
  const base =
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

function normalizedOrigins(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  const origins = new Set<string>();
  for (const value of values) {
    if (typeof value !== "string") continue;
    try {
      const url = new URL(value);
      if (
        ["http:", "https:"].includes(url.protocol) &&
        url.pathname === "/" &&
        !url.search &&
        !url.hash
      ) {
        origins.add(url.origin);
      }
    } catch {
      // Invalid stored values are excluded from the CSP source list.
    }
  }
  return Array.from(origins);
}

function protectFromFraming(response: NextResponse): NextResponse {
  response.headers.set("Content-Security-Policy", "frame-ancestors 'none'");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

async function embedResponse(request: NextRequest): Promise<NextResponse> {
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");

  const token = process.env.WIDGET_POLICY_TOKEN;
  const agentId = request.nextUrl.pathname.split("/")[2];
  if (!token || !agentId) {
    response.headers.set("Content-Security-Policy", "frame-ancestors 'none'");
    return response;
  }

  try {
    const policy = await fetch(
      backendUrl(`/internal/widget-frame-policy/${encodeURIComponent(agentId)}`),
      {
        headers: { "X-Widget-Policy-Token": token },
        cache: "no-store",
      },
    );
    const payload = policy.ok
      ? await policy.json() as { allowed_origins?: unknown }
      : null;
    const origins = normalizedOrigins(payload?.allowed_origins);
    response.headers.set(
      "Content-Security-Policy",
      origins.length
        ? `frame-ancestors ${origins.join(" ")}`
        : "frame-ancestors 'none'",
    );
  } catch {
    response.headers.set("Content-Security-Policy", "frame-ancestors 'none'");
  }
  return response;
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  if (request.nextUrl.pathname.startsWith("/embed/")) {
    return embedResponse(request);
  }

  const hasSession = Boolean(
    request.cookies.get("autorag_access") || request.cookies.get("autorag_refresh"),
  );
  if (request.nextUrl.pathname.startsWith("/dashboard") && !hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return protectFromFraming(NextResponse.redirect(login));
  }
  return protectFromFraming(NextResponse.next());
}

export const config = {
  matcher: ["/((?!api/|_next/|favicon.ico|widget.js).*)"],
};
