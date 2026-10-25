import { clearTokens } from "@/lib/server/backend";

export async function POST(): Promise<Response> {
  await clearTokens();
  return Response.json({ ok: true });
}
