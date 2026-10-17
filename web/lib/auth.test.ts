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
