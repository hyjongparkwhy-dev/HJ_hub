import Link from "next/link";
import { CATEGORY_LABEL, SOURCE_LABEL } from "@/lib/format";
import type { Article } from "@/lib/queries";
import { VoteButtons } from "./vote-buttons";

const TIME = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" });

export function ArticleRow({ a, marker, note }: { a: Article; marker?: string; note?: string | null }) {
  return (
    <li className="article">
      {marker ? <span className="marker" aria-hidden>{marker}</span> : null}
      <div className="article-body">
        <p className="kicker">
          <span>{CATEGORY_LABEL[a.category] ?? a.category}</span>
          <span>{SOURCE_LABEL[a.source] ?? a.source}</span>
          <time dateTime={a.at}>{TIME.format(new Date(a.at))}</time>
        </p>
        <h3>
          <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
        </h3>
        {a.summary ? <p className="summary">{a.summary}</p> : null}
        {note ? <p className="reason">{note}</p> : null}
        <p className="article-actions">
          <VoteButtons itemId={a.id} current={a.vote} />
          <Link href={`/similar/${a.id}`}>비슷한 기사</Link>
        </p>
      </div>
    </li>
  );
}
