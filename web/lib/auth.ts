// Same passcode gate as kid-meal: an HMAC of the passcode is the session cookie.
export const SESSION_COOKIE = "hub_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 180;

const encoder = new TextEncoder();

async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return Array.from(new Uint8Array(signature), (b) => b.toString(16).padStart(2, "0")).join("");
}

function equalHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// The token is derived from the passcode, so changing HUB_PASSCODE signs every device out.
export function sessionToken(passcode: string, secret: string): Promise<string> {
  return hmacHex(secret, `session:${passcode}`);
}

export async function verifySession(token: string | undefined, passcode: string, secret: string): Promise<boolean> {
  if (!token) return false;
  return equalHex(token, await sessionToken(passcode, secret));
}

// Compare digests, not raw strings, so timing does not reveal the passcode length or prefix.
export async function passcodeMatches(input: string, passcode: string, secret: string): Promise<boolean> {
  if (!input) return false;
  return equalHex(await hmacHex(secret, `pass:${input}`), await hmacHex(secret, `pass:${passcode}`));
}

// URL parsing drops tabs and newlines, so "/\t/evil.com" would become "//evil.com"; resolve it the way the browser does.
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/")) return "/";
  const base = "http://in-app.invalid";
  const resolved = new URL(next, base);
  if (resolved.origin !== base) return "/";
  return `${resolved.pathname}${resolved.search}`;
}
