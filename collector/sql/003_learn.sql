-- my-hub stage 4A: why each article was picked, and the daily 👍 rate to see whether learning helps. Safe to re-run.
alter table hub.brief_item add column if not exists reason text;

create or replace view hub.daily_feedback with (security_invoker = true) as
select b.brief_date,
       count(f.vote) as votes,
       count(*) filter (where f.vote = 1) as up,
       round(avg((f.vote = 1)::int)::numeric, 2) as up_rate
from hub.brief b
join hub.brief_item bi on bi.brief_id = b.id
left join hub.feedback f on f.item_id = bi.item_id
group by b.brief_date;

revoke all on hub.daily_feedback from anon, authenticated;
