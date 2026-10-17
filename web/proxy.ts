import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, verifySession } from "@/lib/auth";
import { requireEnv } from "@/lib/env";

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (path === "/login") return NextResponse.next();
  const ok = await verifySession(
    request.cookies.get(SESSION_COOKIE)?.value,
    requireEnv("HUB_PASSCODE"),
    requireEnv("AUTH_SECRET"),
  );
  if (ok) return NextResponse.next();
  // A redirect would hand a server action an HTML page; a plain 401 lets the caller say "signed out".
  if (request.method !== "GET" && request.method !== "HEAD") return new NextResponse(null, { status: 401 });
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${path}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

// Everything but static assets, including server action POSTs to the pages.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico$|icon\\.svg$).*)"],
};
