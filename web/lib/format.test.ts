import { describe, expect, it } from "vitest";
import { dateLabel, percent, searchPatterns, upRate } from "./format";

describe("dateLabel", () => {
  it("names the KST calendar day and weekday", () => {
    expect(dateLabel("2026-10-17")).toBe("10월 17일 토요일");
    expect(dateLabel("2026-10-16")).toBe("10월 16일 금요일");
  });
});

describe("searchPatterns", () => {
  it("turns words into contains patterns and caps their number", () => {
    expect(searchPatterns("  서울  아파트 ")).toEqual(["%서울%", "%아파트%"]);
    expect(searchPatterns("a b c d e f g")).toHaveLength(5);
    expect(searchPatterns("   ")).toEqual([]);
  });

  it("keeps LIKE wildcards literal", () => {
    expect(searchPatterns("100% a_b c\\d")).toEqual(["%100\\%%", "%a\\_b%", "%c\\\\d%"]);
  });
});

describe("upRate", () => {
  it("is null without votes", () => {
    expect(upRate(0, 0)).toBeNull();
    expect(upRate(3, 4)).toBe(0.75);
    expect(percent(0.756)).toBe("76%");
    expect(percent(null)).toBe("–");
  });
});
