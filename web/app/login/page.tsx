import { safeNext } from "@/lib/auth";
import { LoginForm } from "./form";

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  return (
    <main className="login">
      <h1 className="login-title">비밀 문구를 넣어 주세요</h1>
      <LoginForm next={safeNext(typeof next === "string" ? next : null)} />
      <p className="muted">한 번 들어오면 이 기기에서 180일 동안 유지돼요.</p>
    </main>
  );
}
