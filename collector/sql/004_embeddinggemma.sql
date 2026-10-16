-- my-hub: switch hub.item embeddings to EmbeddingGemma (768 dims, half precision).
-- Run with `python -m hub_collect.reembed`, which applies step 1, re-embeds every row, then applies step 2.

-- step 1
alter table hub.item add column if not exists embedding_next extensions.halfvec(768);

-- step 2 (only after every row has embedding_next)
alter table hub.item drop column embedding;
alter table hub.item rename column embedding_next to embedding;
alter table hub.item alter column embedding set not null;
