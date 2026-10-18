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
  yt_claude: "Claude",
  yt_anthropic: "Anthropic",
  yt_routeai: "이동훈의 루트AI",
  yt_aiexplained: "AI Explained",
  yt_aiengineer: "AI Engineer",
  yt_mattwolfe: "Matt Wolfe",
  yt_a16z: "a16z",
  yt_verge: "The Verge",
  yt_mkbhd: "Marques Brownlee",
  yt_svgirl: "Silicon Valley Girl",
  yt_aiadvantage: "The AI Advantage",
  yt_twist: "This Week in Startups",
  yt_allin: "All-In",
  yt_nateherk: "Nate Herk",
  yt_benai: "Ben AI",
  yt_howiai: "How I AI",
  yt_yc: "Y Combinator",
  yt_greg: "Greg Isenberg",
  yt_lenny: "Lenny's Podcast",
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

export interface ReasonLine {
  label: string;
  text: string;
}

/** The collector's "주제: 반도체 · 👍 비슷: <title>" as labelled lines a reader can scan. */
export function reasonLines(reason: string | null): ReasonLine[] {
  return (reason ?? "")
    .split(" · ")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith("주제:")) return { label: "관심 주제", text: part.slice(3).trim() };
      const liked = part.match(/^👍 비슷:\s*(.*)$/u);
      if (liked) return { label: "좋아한 기사와 비슷", text: liked[1] };
      return { label: "", text: part };
    });
}

/** Relevance or similarity (0–1) as a 0–100 number. */
export function points(value: number): number {
  return Math.round(value * 100);
}

/** Groups keep the order in which their first article appears, so the best-ranked topic leads. */
export function groupByCategory<T extends { category: string }>(articles: T[]): { category: string; articles: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const a of articles) groups.set(a.category, [...(groups.get(a.category) ?? []), a]);
  return [...groups].map(([category, list]) => ({ category, articles: list }));
}

/** YouTube links; the collector keeps full videos only (no shorts). */
export function isVideo(url: string): boolean {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return host === "youtube.com" || host === "youtu.be";
  } catch {
    return false;
  }
}
