export const CATEGORY_LABEL: Record<string, string> = { invest: "투자", realestate: "부동산", tech: "기술" };

// Mirrors collector/hub_collect/sources.py.
export const SOURCE_LABEL: Record<string, string> = {
  hankyung_economy: "한국경제",
  hankyung_finance: "한국경제 증권",
  yna_economy: "연합뉴스",
  yna_market: "연합뉴스 마켓",
  chosunbiz_stock: "조선비즈",
  bloomberg_markets: "Bloomberg",
  bloomberg_economics: "Bloomberg",
  cnbc_top: "CNBC",
  wsj_markets: "WSJ",
  ft_markets: "Financial Times",
  hankyung_realestate: "한국경제 부동산",
  heraldcorp_realestate: "헤럴드경제",
  sedaily_realestate: "서울경제",
  mk_realestate: "매일경제",
  asiae_realestate: "아시아경제",
  chosunbiz_realestate: "조선비즈",
  etnews: "전자신문",
  zdnet_kr: "ZDNet Korea",
  hankyung_it: "한국경제 IT",
  theverge: "The Verge",
  techcrunch: "TechCrunch",
  arstechnica: "Ars Technica",
  wired: "WIRED",
  mit_techreview: "MIT Technology Review",
  bloomberg_tech: "Bloomberg",
  cnbc_tech: "CNBC",
  engadget: "Engadget",
  // Removed 2026-10-17 (not news outlets); kept so older briefings still show a name.
  geeknews: "GeekNews",
  hackernews: "Hacker News",
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** "2026-10-17" → "10월 17일 토요일". The date is a calendar day in KST, so it is read without a timezone shift. */
export function dateLabel(isoDay: string): string {
  const [y, m, d] = isoDay.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${m}월 ${d}일 ${weekday}요일`;
}

export const MAX_TERMS = 5;

/** Whitespace-separated words as ILIKE patterns; every word must appear. LIKE wildcards typed by the user are literal. */
export function searchPatterns(query: string): string[] {
  return query
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, MAX_TERMS)
    .map((word) => `%${word.replace(/[\\%_]/g, (c) => `\\${c}`)}%`);
}

/** Share of 👍 among votes, or null when there were none. */
export function upRate(up: number, votes: number): number | null {
  return votes > 0 ? up / votes : null;
}

export function percent(rate: number | null): string {
  return rate === null ? "–" : `${Math.round(rate * 100)}%`;
}
