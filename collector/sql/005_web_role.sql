-- my-hub stage 4B: a login role for the web app that can read briefings and items and record votes, nothing
-- else in the RichRich database. The password is set separately (never stored in this repository):
--   alter role hub_web password '...';
-- Safe to re-run.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'hub_web') then
    create role hub_web login noinherit connection limit 5;
  end if;
end
$$;

grant usage on schema hub to hub_web;
grant usage on schema extensions to hub_web; -- halfvec type and its <=> operator
grant select on hub.item, hub.brief, hub.brief_item, hub.daily_feedback to hub_web;
grant select, insert, update on hub.feedback to hub_web;

-- RLS stays on; these policies open exactly the rows above to this one role.
drop policy if exists hub_web_read on hub.item;
create policy hub_web_read on hub.item for select to hub_web using (true);
drop policy if exists hub_web_read on hub.brief;
create policy hub_web_read on hub.brief for select to hub_web using (true);
drop policy if exists hub_web_read on hub.brief_item;
create policy hub_web_read on hub.brief_item for select to hub_web using (true);
drop policy if exists hub_web_read on hub.feedback;
create policy hub_web_read on hub.feedback for select to hub_web using (true);
drop policy if exists hub_web_vote on hub.feedback;
create policy hub_web_vote on hub.feedback for insert to hub_web with check (vote in (-1, 1));
drop policy if exists hub_web_revote on hub.feedback;
create policy hub_web_revote on hub.feedback for update to hub_web using (true) with check (vote in (-1, 1));
