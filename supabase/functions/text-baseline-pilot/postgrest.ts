import type { PilotDb, PendingRow, FinalPatch, SessionSettings } from "./handler.ts";
import type { EvidenceItem } from "./prompt.ts";
import { RETRIEVAL_LIMIT, UPSTREAM_TIMEOUT_MS } from "./constants.ts";

export type PostgrestConfig = {
  url: string;
  anonKey: string;
  jwt: string;
  fetchImpl: typeof fetch;
  timeoutMs?: number;
};

async function rest<T>(
  config: PostgrestConfig,
  path: string,
  init: RequestInit,
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = config.timeoutMs ?? UPSTREAM_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await config.fetchImpl(`${config.url.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        authorization: `Bearer ${config.jwt}`,
        apikey: config.anonKey,
        "content-type": "application/json",
        ...(init.headers ?? {}),
      },
      redirect: "error",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`postgrest_${response.status}`);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    // Prefer: return=minimal and void RPCs may yield an empty 200/201 body.
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    return JSON.parse(text) as T;
  } finally {
    clearTimeout(timer);
  }
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
          p_limit: RETRIEVAL_LIMIT,
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
    async claimCall(requestId) {
      const data = await rest<boolean>(config, "/rest/v1/rpc/claim_pilot_call", {
        method: "POST",
        body: JSON.stringify({ p_request_id: requestId }),
      });
      return data === true;
    },
    async insertPending(row: PendingRow) {
      await rest(config, "/rest/v1/rpc/insert_pilot_pending", {
        method: "POST",
        body: JSON.stringify({
          p_request_id: row.request_id,
          p_snapshot_id: row.snapshot_id,
          p_condition: row.condition,
          p_question: row.question,
        }),
      });
    },
    async finalize(requestId, _ownerId, patch: FinalPatch) {
      await rest(config, "/rest/v1/rpc/finalize_pilot_result", {
        method: "POST",
        body: JSON.stringify({
          p_request_id: requestId,
          p_status: patch.status,
          p_answer_text: patch.answer_text,
          p_failure_code: patch.failure_code,
          p_evidence_sha256: patch.evidence_sha256,
          p_retrieval_ms: patch.retrieval_ms,
          p_model_http_ms: patch.model_http_ms,
          p_gateway_ms: patch.gateway_ms,
          p_input_tokens: patch.input_tokens,
          p_output_tokens: patch.output_tokens,
        }),
      });
    },
  };
}
