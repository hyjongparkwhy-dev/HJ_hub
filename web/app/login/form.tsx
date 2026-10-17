"use client";

import { useActionState } from "react";
import { login, type LoginState } from "./actions";

const initial: LoginState = { error: null };

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(login, initial);
  return (
    <form action={action} className="login-form">
      <input type="hidden" name="next" value={next} />
      <label htmlFor="passcode">비밀 문구</label>
      <input id="passcode" name="passcode" type="password" autoComplete="current-password" required />
      {state.error ? <p role="alert" className="login-error">{state.error}</p> : null}
      <button type="submit" disabled={pending}>{pending ? "확인하는 중" : "들어가기"}</button>
    </form>
  );
}
