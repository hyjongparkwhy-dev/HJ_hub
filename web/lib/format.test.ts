import { describe, expect, it } from "vitest";
import { dateLabel, groupByCategory, percent, points, reasonLines, searchPatterns, upRate } from "./format";

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

describe("reasonLines", () => {
  it("labels topics and vote matches", () => {
    expect(reasonLines("주제: 반도체 · 👍 비슷: 코스피 반등")).toEqual([
      { label: "관심 주제", text: "반도체" },
      { label: "좋아한 기사와 비슷", text: "코스피 반등" },
    ]);
    expect(reasonLines(null)).toEqual([]);
    expect(reasonLines("새 출처")).toEqual([{ label: "", text: "새 출처" }]);
  });
});

describe("groupByCategory", () => {
  it("orders groups by their first article", () => {
    const rows = [{ category: "realestate", n: 1 }, { category: "invest", n: 2 }, { category: "realestate", n: 3 }];
    expect(groupByCategory(rows).map((g) => [g.category, g.articles.map((a) => a.n)])).toEqual([
      ["realestate", [1, 3]],
      ["invest", [2]],
    ]);
    expect(points(0.536)).toBe(54);
  });
});
