-- Supervised text-baseline pilot snapshot. Do not apply remotely from CI.
-- Owner-scoped RLS. Invoker RPCs pin an empty search_path.

create extension if not exists vector with schema extensions;

create table public.pilot_memory_snapshots (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users (id),
  label text not null,
  fixture_sha256 text not null,
  created_at timestamptz not null default now()
);

create table public.pilot_memory_items (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.pilot_memory_snapshots (id) on delete restrict,
  item_kind text not null check (item_kind in ('fact', 'source_passage')),
  content text not null,
  embedding extensions.vector(384) not null,
  created_at timestamptz not null default now()
);

create table public.pilot_allowlist (
  user_id uuid primary key references auth.users (id),
  deadline timestamptz not null
);

create table public.pilot_session_config (
  id text primary key check (id = 'active'),
  deadline timestamptz not null,
  max_calls integer not null check (max_calls > 0),
  window_seconds integer not null check (window_seconds > 0),
  updated_at timestamptz not null default now()
);

create table public.pilot_request_results (
  request_id uuid primary key,
  owner_id uuid not null references auth.users (id),
  snapshot_id uuid not null references public.pilot_memory_snapshots (id),
  condition text not null check (condition in ('S0', 'S1', 'L0', 'L1')),
  question text not null,
  status text not null check (status in ('pending', 'success', 'failed')),
  answer_text text,
  failure_code text,
  evidence_sha256 text,
  retrieval_ms double precision,
  model_http_ms double precision,
  gateway_ms double precision,
  client_ms double precision,
  first_token_ms double precision,
  input_tokens integer,
  output_tokens integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (first_token_ms is null)
);

create table public.pilot_call_log (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id),
  request_id uuid not null unique,
  called_at timestamptz not null default now()
);

create index pilot_memory_items_snapshot_id_idx
  on public.pilot_memory_items (snapshot_id);

create index pilot_call_log_user_called_idx
  on public.pilot_call_log (user_id, called_at desc);

alter table public.pilot_memory_snapshots enable row level security;
alter table public.pilot_memory_items enable row level security;
alter table public.pilot_allowlist enable row level security;
alter table public.pilot_session_config enable row level security;
alter table public.pilot_request_results enable row level security;
alter table public.pilot_call_log enable row level security;

create or replace function public.pilot_access_is_active()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select exists (
    select 1
    from public.pilot_allowlist a
    where a.user_id = (select auth.uid())
      and a.deadline > now()
  );
$$;

create or replace function public.pilot_session_is_active()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select exists (
    select 1
    from public.pilot_session_config c
    where c.id = 'active'
      and c.deadline > now()
  );
$$;

create or replace function public.pilot_supervised()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select (select public.pilot_access_is_active())
     and (select public.pilot_session_is_active());
$$;

create policy pilot_snapshots_select_own
  on public.pilot_memory_snapshots
  for select
  to authenticated
  using (
    owner_id = (select auth.uid())
    and (select public.pilot_supervised())
  );

create policy pilot_snapshots_insert_own
  on public.pilot_memory_snapshots
  for insert
  to authenticated
  with check (
    owner_id = (select auth.uid())
    and (select public.pilot_supervised())
  );

create policy pilot_items_select_own
  on public.pilot_memory_items
  for select
  to authenticated
  using (
    (select public.pilot_supervised())
    and exists (
      select 1
      from public.pilot_memory_snapshots s
      where s.id = snapshot_id
        and s.owner_id = (select auth.uid())
    )
  );

create policy pilot_items_insert_own
  on public.pilot_memory_items
  for insert
  to authenticated
  with check (
    (select public.pilot_supervised())
    and exists (
      select 1
      from public.pilot_memory_snapshots s
      where s.id = snapshot_id
        and s.owner_id = (select auth.uid())
    )
  );

create policy pilot_allowlist_select_self
  on public.pilot_allowlist
  for select
  to authenticated
  using (user_id = (select auth.uid()));

create policy pilot_session_config_select_active
  on public.pilot_session_config
  for select
  to authenticated
  using (id = 'active');

create policy pilot_results_select_own
  on public.pilot_request_results
  for select
  to authenticated
  using (
    owner_id = (select auth.uid())
    and (select public.pilot_supervised())
  );

-- Result and call-log writes are not granted to authenticated clients.
-- Narrow SECURITY DEFINER RPCs below perform those mutations after auth.uid() checks.

create policy pilot_call_log_select_own
  on public.pilot_call_log
  for select
  to authenticated
  using (
    user_id = (select auth.uid())
    and (select public.pilot_supervised())
  );

create or replace function public.pilot_reject_mutation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  raise exception 'pilot snapshot rows are immutable';
end;
$$;

create trigger pilot_snapshots_immutable
  before update or delete on public.pilot_memory_snapshots
  for each row
  execute function public.pilot_reject_mutation();

create trigger pilot_items_immutable
  before update or delete on public.pilot_memory_items
  for each row
  execute function public.pilot_reject_mutation();

create or replace function public.pilot_session_settings()
returns table (
  deadline timestamptz,
  max_calls integer,
  window_seconds integer
)
language sql
stable
security invoker
set search_path = ''
as $$
  select c.deadline, c.max_calls, c.window_seconds
  from public.pilot_session_config c
  where c.id = 'active'
    and c.deadline > now();
$$;

create or replace function public.verify_pilot_snapshot_ownership(p_snapshot_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select exists (
    select 1
    from public.pilot_memory_snapshots s
    where s.id = p_snapshot_id
      and s.owner_id = (select auth.uid())
      and (select public.pilot_supervised())
  );
$$;

create or replace function public.pilot_recent_call_count(p_window_seconds integer)
returns integer
language sql
stable
security invoker
set search_path = ''
as $$
  select count(*)::integer
  from public.pilot_call_log l
  where l.user_id = (select auth.uid())
    and l.called_at >= now() - make_interval(secs => greatest(coalesce(p_window_seconds, 0), 0));
$$;

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
  with ranked as (
    select
      i.id as item_id,
      i.item_kind,
      i.content,
      ts_rank_cd(
        to_tsvector('simple', i.content),
        plainto_tsquery('simple', coalesce(p_query_text, ''))
      )::double precision as lexical_rank,
      (1 - (i.embedding operator(extensions.<=>) p_query_embedding))::double precision as vector_similarity
    from public.pilot_memory_items i
    inner join public.pilot_memory_snapshots s
      on s.id = i.snapshot_id
    where i.snapshot_id = p_snapshot_id
      and s.owner_id = (select auth.uid())
      and (select public.pilot_supervised())
  )
  select
    ranked.item_id,
    ranked.item_kind,
    ranked.content,
    ranked.lexical_rank,
    ranked.vector_similarity,
    (coalesce(ranked.lexical_rank, 0) + coalesce(ranked.vector_similarity, 0)) as combined_score
  from ranked
  order by combined_score desc, item_id
  limit least(greatest(coalesce(p_limit, 4), 1), 8);
$$;

grant select, insert on table public.pilot_memory_snapshots to authenticated;
grant select, insert on table public.pilot_memory_items to authenticated;
grant select on table public.pilot_allowlist to authenticated;
grant select on table public.pilot_session_config to authenticated;
-- Result and call-log writes go only through narrow invoker RPCs below.
revoke all on table public.pilot_request_results from anon, authenticated;
grant select on table public.pilot_request_results to authenticated;
revoke all on table public.pilot_call_log from anon, authenticated;
grant select on table public.pilot_call_log to authenticated;

create or replace function public.claim_pilot_call(p_request_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  settings record;
begin
  if (select auth.uid()) is null or not (select public.pilot_supervised()) then
    return false;
  end if;
  select c.max_calls, c.window_seconds into settings
  from public.pilot_session_config c
  where c.id = 'active'
    and c.deadline > now();
  if not found then
    return false;
  end if;
  perform pg_advisory_xact_lock(hashtextextended((select auth.uid())::text, 0));
  if (
    select count(*)
    from public.pilot_call_log l
    where l.user_id = (select auth.uid())
      and l.called_at >= now() - make_interval(secs => settings.window_seconds)
  ) >= settings.max_calls then
    return false;
  end if;
  begin
    insert into public.pilot_call_log(user_id, request_id)
    values ((select auth.uid()), p_request_id);
  exception when unique_violation then
    return false;
  end;
  return true;
end;
$$;

create or replace function public.insert_pilot_pending(
  p_request_id uuid,
  p_snapshot_id uuid,
  p_condition text,
  p_question text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null or not (select public.pilot_supervised()) then
    raise exception 'pilot pending insert denied';
  end if;
  if p_condition not in ('S0', 'S1', 'L0', 'L1') then
    raise exception 'invalid pilot condition';
  end if;
  if not exists (
    select 1
    from public.pilot_memory_snapshots s
    where s.id = p_snapshot_id
      and s.owner_id = (select auth.uid())
  ) then
    raise exception 'snapshot not owned by caller';
  end if;
  insert into public.pilot_request_results (
    request_id, owner_id, snapshot_id, condition, question, status
  ) values (
    p_request_id, (select auth.uid()), p_snapshot_id, p_condition, p_question, 'pending'
  );
end;
$$;

create or replace function public.finalize_pilot_result(
  p_request_id uuid,
  p_status text,
  p_answer_text text,
  p_failure_code text,
  p_evidence_sha256 text,
  p_retrieval_ms double precision,
  p_model_http_ms double precision,
  p_gateway_ms double precision,
  p_input_tokens integer,
  p_output_tokens integer
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null or not (select public.pilot_supervised()) then
    raise exception 'pilot finalize denied';
  end if;
  if p_status not in ('success', 'failed') then
    raise exception 'invalid pilot finalize status';
  end if;
  update public.pilot_request_results
  set
    status = p_status,
    answer_text = p_answer_text,
    failure_code = p_failure_code,
    evidence_sha256 = p_evidence_sha256,
    retrieval_ms = p_retrieval_ms,
    model_http_ms = p_model_http_ms,
    gateway_ms = p_gateway_ms,
    first_token_ms = null,
    input_tokens = p_input_tokens,
    output_tokens = p_output_tokens,
    updated_at = now()
  where request_id = p_request_id
    and owner_id = (select auth.uid())
    and status = 'pending';
  if not found then
    raise exception 'pilot finalize target missing';
  end if;
end;
$$;

revoke execute on function public.pilot_reject_mutation() from public, anon;
revoke execute on function public.pilot_access_is_active() from public, anon;
revoke execute on function public.pilot_session_is_active() from public, anon;
revoke execute on function public.pilot_supervised() from public, anon;
revoke execute on function public.pilot_session_settings() from public, anon;
revoke execute on function public.verify_pilot_snapshot_ownership(uuid) from public, anon;
revoke execute on function public.pilot_recent_call_count(integer) from public, anon;
revoke execute on function public.retrieve_pilot_memory(uuid, text, extensions.vector, integer) from public, anon;
revoke execute on function public.claim_pilot_call(uuid) from public, anon;
revoke execute on function public.insert_pilot_pending(uuid, uuid, text, text) from public, anon;
revoke execute on function public.finalize_pilot_result(uuid, text, text, text, text, double precision, double precision, double precision, integer, integer) from public, anon;

grant execute on function public.pilot_access_is_active() to authenticated;
grant execute on function public.pilot_session_is_active() to authenticated;
grant execute on function public.pilot_supervised() to authenticated;
grant execute on function public.pilot_session_settings() to authenticated;
grant execute on function public.verify_pilot_snapshot_ownership(uuid) to authenticated;
grant execute on function public.pilot_recent_call_count(integer) to authenticated;
grant execute on function public.retrieve_pilot_memory(uuid, text, extensions.vector, integer) to authenticated;
grant execute on function public.claim_pilot_call(uuid) to authenticated;
grant execute on function public.insert_pilot_pending(uuid, uuid, text, text) to authenticated;
grant execute on function public.finalize_pilot_result(uuid, text, text, text, text, double precision, double precision, double precision, integer, integer) to authenticated;
