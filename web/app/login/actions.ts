"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { passcodeMatches, safeNext, SESSION_COOKIE, SESSION_MAX_AGE, sessionToken } from "@/lib/auth";
import { requireEnv } from "@/lib/env";

export interface LoginState {
  error: string | null;
}

export async function login(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const passcode = requireEnv("HUB_PASSCODE");
  const secret = requireEnv("AUTH_SECRET");
  const input = String(formData.get("passcode") ?? "");
  if (!(await passcodeMatches(input, passcode, secret))) {
    await new Promise((resolve) => setTimeout(resolve, 800)); // slows down guessing
    return { error: "비밀 문구가 맞지 않아요." };
  }
  (await cookies()).set(SESSION_COOKIE, await sessionToken(passcode, secret), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  redirect(safeNext(String(formData.get("next") ?? "/")));
}
