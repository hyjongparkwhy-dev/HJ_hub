"use server";

import { revalidatePath } from "next/cache";
import { saveVote } from "@/lib/queries";
import { requireSession, Unauthorized } from "@/lib/session";

export type VoteResult = "ok" | "signed-out";

export async function vote(itemId: number, value: 1 | -1): Promise<VoteResult> {
  try {
    await requireSession();
  } catch (e) {
    if (e instanceof Unauthorized) return "signed-out";
    throw e;
  }
  if (!Number.isSafeInteger(itemId) || itemId <= 0 || (value !== 1 && value !== -1)) throw new Error("invalid vote");
  await saveVote(itemId, value);
  revalidatePath("/", "layout");
  return "ok";
}
