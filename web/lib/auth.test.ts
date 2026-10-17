import { describe, expect, it } from "vitest";
import { passcodeMatches, safeNext, sessionToken, verifySession } from "./auth";

describe("passcode gate", () => {
  it("accepts only the passcode and a token made from it", async () => {
    expect(await passcodeMatches("morning", "morning", "s")).toBe(true);
    expect(await passcodeMatches("mornin", "morning", "s")).toBe(false);
    expect(await passcodeMatches("", "morning", "s")).toBe(false);
    const token = await sessionToken("morning", "s");
    expect(await verifySession(token, "morning", "s")).toBe(true);
    expect(await verifySession(token, "changed", "s")).toBe(false);
    expect(await verifySession(undefined, "morning", "s")).toBe(false);
  });

  it("expires sessions and rejects altered issue times", async () => {
    const day = 24 * 60 * 60 * 1000;
    const issued = Date.UTC(2026, 9, 17);
    const token = await sessionToken("morning", "s", issued);
    expect(await verifySession(token, "morning", "s", issued + 179 * day)).toBe(true);
    expect(await verifySession(token, "morning", "s", issued + 181 * day)).toBe(false);
    expect(await verifySession(token, "morning", "s", issued - day)).toBe(false);
    const [time, sig] = token.split(".");
    expect(await verifySession(`${Number(time) + 86400}.${sig}`, "morning", "s", issued + day)).toBe(false);
    // Cookies from before issue times were signed no longer count.
    expect(await verifySession(sig, "morning", "s", issued)).toBe(false);
  });
});

describe("safeNext", () => {
  it("keeps same-site paths and drops everything else", () => {
    expect(safeNext("/search?q=a")).toBe("/search?q=a");
    expect(safeNext("//evil.test")).toBe("/");
    expect(safeNext("/\t/evil.test")).toBe("/");
    expect(safeNext("https://evil.test")).toBe("/");
    expect(safeNext(null)).toBe("/");
  });
});
