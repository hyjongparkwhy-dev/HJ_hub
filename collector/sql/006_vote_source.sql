-- Where each vote came from. A web vote is a deliberate change made after the Telegram message,
-- so the evening Telegram pickup must not overwrite it (Telegram presses carry no time of their own).
-- Existing rows all came from Telegram. Safe to re-run.
alter table hub.feedback add column if not exists source text not null default 'telegram';
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'feedback_source_check') then
    alter table hub.feedback add constraint feedback_source_check check (source in ('telegram', 'web'));
  end if;
end
$$;
