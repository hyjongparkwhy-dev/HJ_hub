-- my-hub stage 3: morning briefings and 👍/👎 feedback, next to hub.item. Safe to re-run.
create table if not exists hub.brief (
  id bigint generated always as identity primary key,
  brief_date date not null unique,
  sent_at timestamptz not null default now(),
  message_id bigint,
  stats jsonb not null
);

create table if not exists hub.brief_item (
  brief_id bigint not null references hub.brief (id) on delete cascade,
  rank smallint not null,
  item_id bigint not null references hub.item (id) on delete cascade,
  score real not null,
  title text not null,
  summary text,
  primary key (brief_id, rank)
);
create index if not exists brief_item_item_idx on hub.brief_item (item_id);

-- One row per article: the last press wins.
create table if not exists hub.feedback (
  item_id bigint primary key references hub.item (id) on delete cascade,
  vote smallint not null check (vote in (-1, 1)),
  voted_at timestamptz not null default now()
);

-- Small key/value state, e.g. the Telegram getUpdates offset.
create table if not exists hub.state (
  key text primary key,
  value jsonb not null
);

alter table hub.brief enable row level security;
alter table hub.brief_item enable row level security;
alter table hub.feedback enable row level security;
alter table hub.state enable row level security;
revoke all on all tables in schema hub from anon, authenticated;
