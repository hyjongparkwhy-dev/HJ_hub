import { connection } from "next/server";
import { searchArticles } from "@/lib/queries";
import { ArticleRow } from "../article";

export default async function SearchPage({ searchParams }: PageProps<"/search">) {
  await connection();
  const { q } = await searchParams;
  const query = typeof q === "string" ? q.trim() : "";
  const results = query ? await searchArticles(query) : [];
  return (
    <main>
      <header className="page-head">
        <h1>
          <small>최근 90일 기사 제목에서</small>
          검색
        </h1>
      </header>
      <form className="search" role="search" action="/search">
        <label htmlFor="q" className="visually-hidden">제목 검색</label>
        <input id="q" name="q" type="search" defaultValue={query} placeholder="여러 단어는 모두 들어간 기사만" />
        <button type="submit">검색</button>
      </form>
      {query ? (
        <p className="note">
          “{query}” {results.length}건{results.length === 50 ? " (최근 50건까지)" : ""}
        </p>
      ) : (
        <p className="note">뜻이 비슷한 기사는 각 기사를 펼쳐 “비슷한 기사”로 보세요.</p>
      )}
      {results.length ? (
        <ol className="panel">
          {results.map((a) => (
            <ArticleRow key={a.id} a={a} withCategory />
          ))}
        </ol>
      ) : null}
    </main>
  );
}
