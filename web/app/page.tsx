import { connection } from "next/server";
import { CATEGORY_LABEL, dateLabel, groupByCategory, percent, upRate } from "@/lib/format";
import { feedbackTrend, recentBriefs, type Brief } from "@/lib/queries";
import { ArticleRow, LeadArticle } from "./article";

function Groups({ brief, skipFirst }: { brief: Brief; skipFirst: boolean }) {
  const max = Math.max(...brief.articles.map((a) => a.score));
  const rest = skipFirst ? brief.articles.slice(1) : brief.articles;
  return groupByCategory(rest).map((g) => (
    <section key={g.category} className="group">
      <h3>
        {CATEGORY_LABEL[g.category] ?? g.category}
        <span>{g.articles.length}건</span>
      </h3>
      <ol className="panel">
        {g.articles.map((a) => (
          <ArticleRow key={a.id} a={a} reason={a.reason} meter={{ value: a.score, max, label: "관련도" }} />
        ))}
      </ol>
    </section>
  ));
}

export default async function BriefingsPage() {
  await connection(); // always read the latest briefing and votes
  const [briefs, trend] = await Promise.all([recentBriefs(), feedbackTrend()]);
  const [today, ...earlier] = briefs;
  const rate = upRate(trend.thisWeek.up, trend.thisWeek.votes);
  return (
    <main>
      <header className="page-head">
        <h1>
          <small>{today ? "아침 브리핑" : "브리핑"}</small>
          {today ? dateLabel(today.day).replace(/ \S+요일$/, "") : "아직 없어요"}
        </h1>
        <p className="rate" title={`그 전 7일 ${percent(upRate(trend.lastWeek.up, trend.lastWeek.votes))} (${trend.lastWeek.votes}표)`}>
          <b>{percent(rate)}</b>
          최근 7일 좋아요 · {trend.thisWeek.votes}표
        </p>
      </header>
      {today ? (
        <>
          <LeadArticle
            a={today.articles[0]}
            reason={today.articles[0].reason}
            meter={{ value: today.articles[0].score, max: today.articles[0].score, label: "관련도" }}
          />
          <Groups brief={today} skipFirst />
        </>
      ) : (
        <p className="empty">매일 오전 9시에 그날의 기사 10건이 여기에 올라와요.</p>
      )}
      {earlier.length ? (
        <section className="earlier">
          <h2>지난 브리핑</h2>
          {earlier.map((brief) => (
            <details key={brief.day} className="day">
              <summary>
                {dateLabel(brief.day)}
                <span>{brief.articles.length}건</span>
              </summary>
              <Groups brief={brief} skipFirst={false} />
            </details>
          ))}
        </section>
      ) : null}
    </main>
  );
}
