"use client";

import { useOptimistic, useState, useTransition } from "react";
import type { Vote } from "@/lib/queries";
import { vote } from "./actions";

export function VoteButtons({ itemId, current }: { itemId: number; current: Vote }) {
  const [shown, setShown] = useOptimistic<Vote, Vote>(current, (_, next) => next);
  const [pending, start] = useTransition();
  const [problem, setProblem] = useState<string | null>(null);
  const press = (value: 1 | -1) =>
    start(async () => {
      setProblem(null);
      setShown(value);
      try {
        if ((await vote(itemId, value)) === "signed-out") setProblem("로그인이 풀렸어요. 새로고침 후 다시 눌러 주세요.");
      } catch {
        // The optimistic state rolls back on its own; say so instead of failing silently.
        setProblem("저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.");
      }
    });
  return (
    <span className="votes" aria-busy={pending}>
      <button type="button" aria-pressed={shown === 1} aria-label="좋아요" onClick={() => press(1)}>
        👍
      </button>
      <button type="button" aria-pressed={shown === -1} aria-label="별로예요" onClick={() => press(-1)}>
        👎
      </button>
      {problem ? <span role="alert" className="vote-problem">{problem}</span> : null}
    </span>
  );
}
