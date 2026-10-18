import Link from "next/link";
import { CATEGORY_LABEL, SOURCE_LABEL, isVideo, points, reasonLines } from "@/lib/format";
import type { Article } from "@/lib/queries";
import { VoteButtons } from "./vote-buttons";

const TIME = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" });

/** A 0–1 value shown as a number with a bar; `max` scales the bar so the day's best fills it. */
export interface Meter {
  value: number;
  max: number;
  label: string; // what the number means, for screen readers
}

function Meta({ a, withCategory }: { a: Article; withCategory: boolean }) {
  return (
    <>
      {withCategory ? `${isVideo(a.url) ? "영상" : (CATEGORY_LABEL[a.category] ?? a.category)} · ` : null}
      {SOURCE_LABEL[a.source] ?? a.source} · <time dateTime={a.at}>{TIME.format(new Date(a.at))}</time>
    </>
  );
}

function Details({ a, reason }: { a: Article; reason?: string | null }) {
  const lines = reasonLines(reason ?? null);
  return (
    <>
      {a.summary ? <p className="summary">{a.summary}</p> : null}
      {lines.length ? (
        <ul className="why">
          {lines.map((l) => (
            <li key={l.label + l.text}>
              {l.label ? <span>{l.label}</span> : null}
              {l.text}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="actions">
        <div className="links">
          <a href={a.url} target="_blank" rel="noopener noreferrer">원문 보기</a>
          <Link href={`/similar/${a.id}`}>비슷한 기사</Link>
        </div>
        <VoteButtons itemId={a.id} current={a.vote} />
      </div>
    </>
  );
}

/** The day's first pick, open from the start. */
export function LeadArticle({ a, meter, reason }: { a: Article; meter?: Meter; reason?: string | null }) {
  return (
    <article className="lead">
      <p className="lead-meta">
        <span><Meta a={a} withCategory /></span>
        {meter ? <b aria-label={`${meter.label} ${points(meter.value)}`}>{points(meter.value)}</b> : null}
      </p>
      <h2>
        <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
      </h2>
      <Details a={a} reason={reason} />
    </article>
  );
}

/** A row that opens in place; without JavaScript it still works as a native disclosure. */
export function ArticleRow({ a, meter, reason, withCategory = false }: { a: Article; meter?: Meter; reason?: string | null; withCategory?: boolean }) {
  return (
    <li className="row">
      <details>
        <summary>
          <span className="row-text">
            <span className="row-title">{a.title}</span>
            <span className="row-meta"><Meta a={a} withCategory={withCategory} /></span>
          </span>
          {meter ? (
            <span className="meter" aria-label={`${meter.label} ${points(meter.value)}`}>
              <b>{points(meter.value)}</b>
              <i style={{ width: `${Math.min(100, (meter.value / meter.max) * 100)}%` }} />
            </span>
          ) : null}
        </summary>
        <div className="row-body">
          <Details a={a} reason={reason} />
        </div>
      </details>
    </li>
  );
}
