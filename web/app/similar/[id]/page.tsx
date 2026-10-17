import { notFound } from "next/navigation";
import { connection } from "next/server";
import { similarArticles } from "@/lib/queries";
import { ArticleRow } from "../../article";

export default async function SimilarPage({ params }: PageProps<"/similar/[id]">) {
  await connection();
  const id = Number((await params).id);
  if (!Number.isSafeInteger(id) || id <= 0) notFound();
  const { base, similar } = await similarArticles(id);
  if (!base) notFound();
  return (
    <main>
      <section className="edition">
        <h2>이 기사와</h2>
        <ol className="plain">
          <ArticleRow a={base} />
        </ol>
      </section>
      <section className="edition">
        <h2>뜻이 비슷한 기사</h2>
        <ol className="plain">
          {similar.map((a) => (
            <ArticleRow key={a.id} a={a} marker={`${Math.round(a.similarity * 100)}`} />
          ))}
        </ol>
        <p className="muted">숫자는 내용이 비슷한 정도(100에 가까울수록 같은 이야기)입니다.</p>
      </section>
    </main>
  );
}
