-- my-hub stage 2: news items with embeddings, in the RichRich project. Safe to re-run.
create extension if not exists vector with schema extensions;
create schema if not exists hub;

create table if not exists hub.item (
  id bigint generated always as identity primary key,
  url text not null unique,
  source text not null,
  category text not null check (category in ('invest', 'realestate', 'tech')),
  title text not null,
  title_key text not null,
  summary text,
  published_at timestamptz,
  fetched_at timestamptz not null default now(),
  embedding extensions.vector(384) not null
);
create index if not exists item_published_idx on hub.item (published_at desc);
create index if not exists item_fetched_idx on hub.item (fetched_at);
create index if not exists item_title_key_idx on hub.item (title_key);

create table if not exists hub.run (
  id bigint generated always as identity primary key,
  ran_at timestamptz not null default now(),
  stats jsonb not null
);

-- Only the collector (database owner role) touches these; the web API keys get nothing.
alter table hub.item enable row level security;
alter table hub.run enable row level security;
revoke all on schema hub from anon, authenticated;
