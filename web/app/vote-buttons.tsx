"use client";

import { useOptimistic, useTransition } from "react";
import type { Vote } from "@/lib/queries";
import { vote } from "./actions";

export function VoteButtons({ itemId, current }: { itemId: number; current: Vote }) {
  const [shown, setShown] = useOptimistic<Vote, Vote>(current, (_, next) => next);
  const [pending, start] = useTransition();
  const press = (value: 1 | -1) =>
    start(async () => {
      setShown(value);
      await vote(itemId, value);
    });
  return (
    <span className="votes" aria-busy={pending}>
      <button type="button" aria-pressed={shown === 1} aria-label="좋아요" onClick={() => press(1)}>
        👍
      </button>
      <button type="button" aria-pressed={shown === -1} aria-label="별로예요" onClick={() => press(-1)}>
        👎
      </button>
    </span>
  );
}
