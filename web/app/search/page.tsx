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
      <form className="search" role="search" action="/search">
        <label htmlFor="q" className="visually-hidden">제목 검색</label>
        <input id="q" name="q" type="search" defaultValue={query} placeholder="제목에 들어간 말 (여러 단어는 모두 포함)" />
        <button type="submit">검색</button>
      </form>
      {query ? (
        <p className="muted result-count">
          “{query}” {results.length}건{results.length === 50 ? " (최근 50건까지)" : ""} · 최근 180일 수집분
        </p>
      ) : (
        <p className="muted result-count">최근 180일 동안 모은 기사 제목에서 찾습니다. 뜻이 비슷한 기사는 각 기사의 “비슷한 기사”로 보세요.</p>
      )}
      <ol className="plain">
        {results.map((a) => (
          <ArticleRow key={a.id} a={a} />
        ))}
      </ol>
    </main>
  );
}
