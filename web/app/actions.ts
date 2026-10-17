"use server";

import { revalidatePath } from "next/cache";
import { saveVote } from "@/lib/queries";

// proxy.ts already requires the session cookie for every POST to a page, so this only validates input.
export async function vote(itemId: number, value: 1 | -1): Promise<void> {
  if (!Number.isSafeInteger(itemId) || itemId <= 0 || (value !== 1 && value !== -1)) throw new Error("invalid vote");
  await saveVote(itemId, value);
  revalidatePath("/", "layout");
}
