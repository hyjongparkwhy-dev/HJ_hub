import { cookies } from "next/headers";
import { SESSION_COOKIE, verifySession } from "./auth";
import { requireEnv } from "./env";

export class Unauthorized extends Error {}

// Server actions are reachable by POST from any route, so each one checks the session itself
// instead of relying on proxy.ts alone.
export async function requireSession(): Promise<void> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!(await verifySession(token, requireEnv("HUB_PASSCODE"), requireEnv("AUTH_SECRET")))) throw new Unauthorized();
}
