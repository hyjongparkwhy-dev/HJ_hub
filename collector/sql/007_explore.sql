-- Marks the briefing slots filled from outside the owner's usual interests (see rank.explore_picks).
-- The web role already reads hub.brief_item; the new column needs no extra grant. Safe to re-run.
alter table hub.brief_item add column if not exists explore boolean not null default false;
