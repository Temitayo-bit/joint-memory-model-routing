import type { PilotDb, PendingRow, FinalPatch, SessionSettings } from "./handler.ts";
import type { EvidenceItem } from "./prompt.ts";

export type PostgrestConfig = {
  url: string;
  anonKey: string;
  jwt: string;
  fetchImpl: typeof fetch;
};

async function rest<T>(
  config: PostgrestConfig,
  path: string,
  init: RequestInit,
): Promise<T> {
  const response = await config.fetchImpl(`${config.url.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${config.jwt}`,
      apikey: config.anonKey,
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
    redirect: "error",
  });
  if (!response.ok) {
    throw new Error(`postgrest_${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return await response.json() as T;
}

export function createPostgrestDb(config: PostgrestConfig): PilotDb {
  return {
    async accessIsActive() {
      const data = await rest<boolean>(config, "/rest/v1/rpc/pilot_access_is_active", {
        method: "POST",
        body: "{}",
      });
      return data === true;
    },
    async sessionSettings() {
      const data = await rest<SessionSettings[]>(config, "/rest/v1/rpc/pilot_session_settings", {
        method: "POST",
        body: "{}",
      });
      return data?.[0] ?? null;
    },
    async verifySnapshotOwnership(_userId, snapshotId) {
      const data = await rest<boolean>(config, "/rest/v1/rpc/verify_pilot_snapshot_ownership", {
        method: "POST",
        body: JSON.stringify({ p_snapshot_id: snapshotId }),
      });
      return data === true;
    },
    async retrieveMemory(_userId, snapshotId, question, embedding) {
      const data = await rest<EvidenceItem[]>(config, "/rest/v1/rpc/retrieve_pilot_memory", {
        method: "POST",
        body: JSON.stringify({
          p_snapshot_id: snapshotId,
          p_query_text: question,
          p_query_embedding: embedding,
          p_limit: 4,
        }),
      });
      return data ?? [];
    },
    async findResult(requestId) {
      const data = await rest<Array<{ status: string }>>(
        config,
        `/rest/v1/pilot_request_results?request_id=eq.${encodeURIComponent(requestId)}&select=status`,
        { method: "GET" },
      );
      return data[0] ?? null;
    },
    async countRecentCalls(_userId, windowSeconds) {
      const data = await rest<number>(config, "/rest/v1/rpc/pilot_recent_call_count", {
        method: "POST",
        body: JSON.stringify({ p_window_seconds: windowSeconds }),
      });
      return typeof data === "number" ? data : 0;
    },
    async recordCall(userId, requestId, nowMs) {
      await rest(config, "/rest/v1/pilot_call_log", {
        method: "POST",
        headers: { Prefer: "return=minimal" },
        body: JSON.stringify({
          user_id: userId,
          request_id: requestId,
          called_at: new Date(nowMs).toISOString(),
        }),
      });
    },
    async insertPending(row: PendingRow) {
      await rest(config, "/rest/v1/pilot_request_results", {
        method: "POST",
        headers: { Prefer: "return=minimal" },
        body: JSON.stringify({
          request_id: row.request_id,
          owner_id: row.owner_id,
          snapshot_id: row.snapshot_id,
          condition: row.condition,
          question: row.question,
          status: "pending",
        }),
      });
    },
    async finalize(requestId, ownerId, patch: FinalPatch) {
      await rest(
        config,
        `/rest/v1/pilot_request_results?request_id=eq.${encodeURIComponent(requestId)}&owner_id=eq.${encodeURIComponent(ownerId)}&status=eq.pending`,
        {
          method: "PATCH",
          headers: { Prefer: "return=minimal" },
          body: JSON.stringify({
            status: patch.status,
            answer_text: patch.answer_text,
            failure_code: patch.failure_code,
            evidence_sha256: patch.evidence_sha256,
            retrieval_ms: patch.retrieval_ms,
            model_http_ms: patch.model_http_ms,
            gateway_ms: patch.gateway_ms,
            first_token_ms: patch.first_token_ms,
            input_tokens: patch.input_tokens,
            output_tokens: patch.output_tokens,
            updated_at: new Date().toISOString(),
          }),
        },
      );
    },
  };
}
