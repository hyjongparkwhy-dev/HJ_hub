"use client";

import { useOptimistic, useState, useTransition } from "react";
import type { Vote } from "@/lib/queries";
import { vote } from "./actions";

const UP_PATH =
  "M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z";

function Thumb({ down }: { down?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" style={down ? { transform: "rotate(180deg)" } : undefined}>
      <path d="M7 10v12" />
      <path d={UP_PATH} />
    </svg>
  );
}

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
      {problem ? <span role="alert" className="vote-problem">{problem}</span> : null}
      <button type="button" className="up" aria-pressed={shown === 1} aria-label="좋아요" onClick={() => press(1)}>
        <Thumb />
      </button>
      <button type="button" className="down" aria-pressed={shown === -1} aria-label="별로예요" onClick={() => press(-1)}>
        <Thumb down />
      </button>
    </span>
  );
}
