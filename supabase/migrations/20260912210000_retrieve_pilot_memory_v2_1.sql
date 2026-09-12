-- pilot_hybrid_v2_1: same snapshot-local IDF token overlap + vector hybrid as
-- pilot_hybrid_v2, with a fixed 127-word English stopword filter applied before
-- query/document token sets and document frequencies.
-- Stopword identity: postgresql_17_english_snowball
-- Source: PostgreSQL REL_17_STABLE src/backend/snowball/stopwords/english.stop
-- Does not alter tables, RLS, grants, or other RPCs.
-- Does not edit the already-applied v2 migration; this is a new replace.
-- Remote apply is operator/Codex work; this file is not executed by CI.

create or replace function public.retrieve_pilot_memory(
  p_snapshot_id uuid,
  p_query_text text,
  p_query_embedding extensions.vector(384),
  p_limit integer default 4
)
returns table (
  item_id uuid,
  item_kind text,
  content text,
  lexical_rank double precision,
  vector_similarity double precision,
  combined_score double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
  with english_stopwords as (
    select unnest(array[
      'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
      'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
      'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
      'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who',
      'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
      'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
      'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the',
      'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while',
      'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
      'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to',
      'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
      'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
      'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few',
      'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
      'only', 'own', 'same', 'so', 'than', 'too', 'very', 's',
      't', 'can', 'will', 'just', 'don', 'should', 'now'
    ]::text[]) as token
  ),
  scoped_items as (
    select
      i.id as item_id,
      i.item_kind,
      i.content,
      i.embedding
    from public.pilot_memory_items i
    inner join public.pilot_memory_snapshots s
      on s.id = i.snapshot_id
    where i.snapshot_id = p_snapshot_id
      and s.owner_id = (select auth.uid())
      and (select public.pilot_supervised())
  ),
  n_docs as (
    select count(*)::double precision as n
    from scoped_items
  ),
  item_tokens as (
    select distinct
      si.item_id,
      lower(m[1]) as token
    from scoped_items si
    cross join lateral regexp_matches(si.content, '[A-Za-z0-9]+', 'g') as m
    where length(m[1]) > 0
      and not exists (
        select 1
        from english_stopwords sw
        where sw.token = lower(m[1])
      )
  ),
  token_df as (
    select
      token,
      count(*)::double precision as df
    from item_tokens
    group by token
  ),
  query_tokens as (
    select distinct lower(m[1]) as token
    from regexp_matches(coalesce(p_query_text, ''), '[A-Za-z0-9]+', 'g') as m
    where length(m[1]) > 0
      and not exists (
        select 1
        from english_stopwords sw
        where sw.token = lower(m[1])
      )
  ),
  query_idf as (
    select
      qt.token,
      (
        ln(((select n from n_docs) + 1.0) / (coalesce(td.df, 0.0) + 1.0)) + 1.0
      )::double precision as idf
    from query_tokens qt
    left join token_df td
      on td.token = qt.token
  ),
  query_denom as (
    select coalesce(sum(idf), 0.0)::double precision as denom
    from query_idf
  ),
  item_lexical as (
    select
      it.item_id,
      coalesce(sum(qi.idf), 0.0)::double precision as idf_mass
    from item_tokens it
    inner join query_idf qi
      on qi.token = it.token
    group by it.item_id
  ),
  ranked as (
    select
      si.item_id,
      si.item_kind,
      si.content,
      case
        when qd.denom <= 0 then 0::double precision
        else (coalesce(il.idf_mass, 0.0) / qd.denom)::double precision
      end as lexical_rank,
      (1 - (si.embedding operator(extensions.<=>) p_query_embedding))::double precision
        as vector_similarity
    from scoped_items si
    cross join query_denom qd
    left join item_lexical il
      on il.item_id = si.item_id
  )
  select
    ranked.item_id,
    ranked.item_kind,
    ranked.content,
    ranked.lexical_rank,
    ranked.vector_similarity,
    (coalesce(ranked.lexical_rank, 0) + coalesce(ranked.vector_similarity, 0))
      as combined_score
  from ranked
  order by combined_score desc, item_id
  limit least(greatest(coalesce(p_limit, 4), 1), 8);
$$;

comment on function public.retrieve_pilot_memory(uuid, text, extensions.vector, integer) is
  'pilot_hybrid_v2_1: snapshot_idf_token_overlap with postgresql_17_english_snowball stopwords + cosine similarity; default limit 4, cap 8';
