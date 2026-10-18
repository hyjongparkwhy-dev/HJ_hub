import { getSql } from "./db";
import { searchPatterns } from "./format";

export type Vote = 1 | -1 | null;

export interface Article {
  id: number;
  url: string;
  category: string;
  source: string;
  title: string;
  summary: string | null;
  at: string; // ISO timestamp: published, or fetched when the feed gave no date
  vote: Vote;
}

export interface BriefArticle extends Article {
  rank: number;
  reason: string | null;
  score: number; // 0–1 relevance the briefing ranked by
  explore: boolean; // picked from outside the owner's usual interests
}

export interface Brief {
  day: string; // "YYYY-MM-DD" in KST
  articles: BriefArticle[];
}

export interface SimilarArticle extends Article {
  similarity: number;
}

const BRIEF_DAYS = 14;
const SEARCH_LIMIT = 50;
const SIMILAR_LIMIT = 10;

type Row = Omit<Article, "id" | "vote" | "at"> & { id: string | number; vote: number | null; at: Date };

function article(r: Row): Article {
  return {
    id: Number(r.id),
    url: r.url,
    category: r.category,
    source: r.source,
    title: r.title,
    summary: r.summary,
    at: r.at.toISOString(),
    vote: r.vote === 1 || r.vote === -1 ? r.vote : null,
  };
}

export async function recentBriefs(): Promise<Brief[]> {
  const sql = getSql();
  // Briefing rows keep Gemini's Korean title and summary; the item keeps the feed's original.
  const rows = await sql<(Row & { day: string; rank: number; reason: string | null; score: number; explore: boolean })[]>`
    select b.brief_date::text as day, bi.rank, bi.reason, bi.score, bi.explore, i.id, i.url, i.category, i.source,
           bi.title, coalesce(bi.summary, i.summary) as summary,
           coalesce(i.published_at, i.fetched_at) as at, f.vote
    from hub.brief b
    join hub.brief_item bi on bi.brief_id = b.id
    join hub.item i on i.id = bi.item_id
    left join hub.feedback f on f.item_id = i.id
    where b.brief_date > (now() at time zone 'Asia/Seoul')::date - ${BRIEF_DAYS}::int
    order by b.brief_date desc, bi.rank`;
  const briefs: Brief[] = [];
  for (const r of rows) {
    if (briefs.at(-1)?.day !== r.day) briefs.push({ day: r.day, articles: [] });
    briefs.at(-1)!.articles.push({ ...article(r), rank: r.rank, reason: r.reason, score: Number(r.score), explore: r.explore });
  }
  return briefs;
}

export async function searchArticles(query: string): Promise<Article[]> {
  const patterns = searchPatterns(query);
  if (patterns.length === 0) return [];
  const sql = getSql();
  const rows = await sql<Row[]>`
    select i.id, i.url, i.category, i.source, i.title, i.summary,
           coalesce(i.published_at, i.fetched_at) as at, f.vote
    from hub.item i
    left join hub.feedback f on f.item_id = i.id
    where i.title ilike all(${patterns}::text[])
    order by coalesce(i.published_at, i.fetched_at) desc
    limit ${SEARCH_LIMIT}`;
  return rows.map(article);
}

export async function similarArticles(id: number): Promise<{ base: Article | null; similar: SimilarArticle[] }> {
  const sql = getSql();
  const [base] = await sql<Row[]>`
    select i.id, i.url, i.category, i.source, i.title, i.summary,
           coalesce(i.published_at, i.fetched_at) as at, f.vote
    from hub.item i left join hub.feedback f on f.item_id = i.id
    where i.id = ${id}`;
  if (!base) return { base: null, similar: [] };
  // The operator lives in the extensions schema, which is not on hub_web's search path.
  const rows = await sql<(Row & { similarity: number })[]>`
    select i.id, i.url, i.category, i.source, i.title, i.summary,
           coalesce(i.published_at, i.fetched_at) as at, f.vote,
           1 - (i.embedding operator(extensions.<=>) b.embedding) as similarity
    from hub.item i
    cross join (select embedding from hub.item where id = ${id}) b
    left join hub.feedback f on f.item_id = i.id
    where i.id <> ${id}
    order by i.embedding operator(extensions.<=>) b.embedding
    limit ${SIMILAR_LIMIT}`;
  return { base: article(base), similar: rows.map((r) => ({ ...article(r), similarity: Number(r.similarity) })) };
}

export interface FeedbackTrend {
  thisWeek: { up: number; votes: number };
  lastWeek: { up: number; votes: number };
}

export async function feedbackTrend(): Promise<FeedbackTrend> {
  const sql = getSql();
  const [r] = await sql<{ up1: string; votes1: string; up2: string; votes2: string }[]>`
    select coalesce(sum(up) filter (where brief_date > (now() at time zone 'Asia/Seoul')::date - 7), 0) as up1,
           coalesce(sum(votes) filter (where brief_date > (now() at time zone 'Asia/Seoul')::date - 7), 0) as votes1,
           coalesce(sum(up) filter (where brief_date <= (now() at time zone 'Asia/Seoul')::date - 7), 0) as up2,
           coalesce(sum(votes) filter (where brief_date <= (now() at time zone 'Asia/Seoul')::date - 7), 0) as votes2
    from hub.daily_feedback
    where brief_date > (now() at time zone 'Asia/Seoul')::date - 14`;
  return {
    thisWeek: { up: Number(r.up1), votes: Number(r.votes1) },
    lastWeek: { up: Number(r.up2), votes: Number(r.votes2) },
  };
}

export async function saveVote(itemId: number, vote: 1 | -1): Promise<void> {
  const sql = getSql();
  await sql`
    insert into hub.feedback (item_id, vote, source) values (${itemId}, ${vote}, 'web')
    on conflict (item_id) do update set vote = excluded.vote, voted_at = now(), source = 'web'`;
}
