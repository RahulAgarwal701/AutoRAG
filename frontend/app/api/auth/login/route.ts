import { authenticate } from "@/lib/server/backend";

export async function POST(request: Request): Promise<Response> {
  return authenticate("login", await request.json());
}
