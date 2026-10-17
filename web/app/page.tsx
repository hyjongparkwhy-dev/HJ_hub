import { connection } from "next/server";
import { dateLabel, percent, upRate } from "@/lib/format";
import { feedbackTrend, recentBriefs } from "@/lib/queries";
import { ArticleRow } from "./article";

export default async function BriefingsPage() {
  await connection(); // always read the latest briefing and votes
  const [briefs, trend] = await Promise.all([recentBriefs(), feedbackTrend()]);
  return (
    <main>
      <section className="trend" aria-label="👍 비율">
        <p>
          최근 7일 👍 <strong>{percent(upRate(trend.thisWeek.up, trend.thisWeek.votes))}</strong>
          <span className="muted"> ({trend.thisWeek.votes}표)</span>
        </p>
        <p className="muted">
          그 전 7일 {percent(upRate(trend.lastWeek.up, trend.lastWeek.votes))} ({trend.lastWeek.votes}표)
        </p>
      </section>
      {briefs.length === 0 ? <p className="empty">아직 브리핑이 없어요. 매일 오전 9시에 나옵니다.</p> : null}
      {briefs.map((brief) => (
        <section key={brief.day} className="edition">
          <h2>{dateLabel(brief.day)}</h2>
          <ol>
            {brief.articles.map((a) => (
              <ArticleRow key={a.id} a={a} marker={String(a.rank)} note={a.reason} />
            ))}
          </ol>
        </section>
      ))}
    </main>
  );
}
