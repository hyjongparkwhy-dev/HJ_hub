import { notFound } from "next/navigation";
import { connection } from "next/server";
import { similarArticles } from "@/lib/queries";
import { ArticleRow, LeadArticle } from "../../article";

export default async function SimilarPage({ params }: PageProps<"/similar/[id]">) {
  await connection();
  const id = Number((await params).id);
  if (!Number.isSafeInteger(id) || id <= 0) notFound();
  const { base, similar } = await similarArticles(id);
  if (!base) notFound();
  return (
    <main>
      <header className="page-head">
        <h1>
          <small>이 기사와</small>
          비슷한 기사
        </h1>
      </header>
      <LeadArticle a={base} />
      <section className="group">
        <h3>
          내용이 가까운 순
          <span>100이면 같은 이야기</span>
        </h3>
        <ol className="panel">
          {similar.map((a) => (
            <ArticleRow key={a.id} a={a} withCategory meter={{ value: a.similarity, max: 1, label: "비슷한 정도" }} />
          ))}
        </ol>
      </section>
    </main>
  );
}
