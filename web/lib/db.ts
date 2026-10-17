import postgres from "postgres";
import { requireEnv } from "./env";

export type Sql = ReturnType<typeof postgres>;

const holder = globalThis as typeof globalThis & { hubSql?: Sql };

// HUB_WEB_DATABASE_URL logs in as hub_web (collector/sql/005_web_role.sql): read items and briefings, write votes.
// prepare: false because the Supabase pooler cannot keep prepared statements.
export function getSql(): Sql {
  holder.hubSql ??= postgres(requireEnv("HUB_WEB_DATABASE_URL"), { prepare: false, max: 1, idle_timeout: 20 });
  return holder.hubSql;
}
