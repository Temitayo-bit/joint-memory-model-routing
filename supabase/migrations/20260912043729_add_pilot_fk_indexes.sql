-- Cover unindexed foreign keys reported by Supabase advisors.
-- Index-only change: do not alter RLS policies, grants, or RPC permissions.

create index pilot_memory_snapshots_owner_id_idx
  on public.pilot_memory_snapshots (owner_id);

create index pilot_request_results_owner_id_idx
  on public.pilot_request_results (owner_id);

create index pilot_request_results_snapshot_id_idx
  on public.pilot_request_results (snapshot_id);
