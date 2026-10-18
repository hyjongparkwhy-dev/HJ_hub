import { connection } from "next/server";
import { CATEGORY_LABEL, dateLabel, groupByCategory, isVideo, percent, upRate } from "@/lib/format";
import { feedbackTrend, recentBriefs, type Brief } from "@/lib/queries";
import { ArticleRow, LeadArticle } from "./article";

function Groups({ brief, skipFirst }: { brief: Brief; skipFirst: boolean }) {
  const explored = brief.articles.filter((a) => a.explore);
  const videos = brief.articles.filter((a) => !a.explore && isVideo(a.url));
  const usual = brief.articles.filter((a) => !a.explore && !isVideo(a.url));
  const max = Math.max(...usual.map((a) => a.score));
  return (
    <>
      {groupByCategory(skipFirst ? usual.slice(1) : usual).map((g) => (
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
      ))}
      {videos.length ? (
        <section className="group videos">
          <h3>
            영상
            <span>AI·테크 채널의 새 영상</span>
          </h3>
          <ol className="panel">
            {videos.map((a) => (
              <ArticleRow key={a.id} a={a} />
            ))}
          </ol>
        </section>
      ) : null}
      {explored.length ? (
        <section className="group explore">
          <h3>
            새로운 주제
            <span>평소 관심 밖에서 골랐어요</span>
          </h3>
          <ol className="panel">
            {explored.map((a) => (
              <ArticleRow key={a.id} a={a} withCategory />
            ))}
          </ol>
          <p className="note">마음에 들면 좋아요를 눌러 주세요. 비슷한 주제가 앞으로 더 나와요.</p>
        </section>
      ) : null}
    </>
  );
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
        <p className="rate" title={`그 전 7일: 투표 ${trend.lastWeek.votes}개 중 좋아요 ${percent(upRate(trend.lastWeek.up, trend.lastWeek.votes))}`}>
          <b>{percent(rate)}</b>
          최근 7일 투표 {trend.thisWeek.votes}개 중 좋아요
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
        <p className="empty">매일 오전 9시에 그날의 기사 20건이 여기에 올라와요.</p>
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
