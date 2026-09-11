import { evidenceCanonical } from "./evidence.ts";
import { MAX_REQUEST_BYTES, type Condition } from "./constants.ts";
import {
  assertApplicationUserJwt,
  assertPilotAccess,
  allowedCorsOrigin,
  bearerToken,
  corsHeaders,
  decodeJwtPayload,
  readServerConfig,
} from "./access.ts";
import { buildModelPayload, callModelOnce } from "./model_client.ts";
import { buildMessages, sanitizeFailure, shouldRetrieve, type EvidenceItem } from "./prompt.ts";
import { parsePilotBody, PilotValidationError, rejectOversized } from "./validate.ts";

export type SessionSettings = {
  deadline: string;
  max_calls: number;
  window_seconds: number;
};

export type PilotDb = {
  accessIsActive(userId: string): Promise<boolean>;
  sessionSettings(): Promise<SessionSettings | null>;
  verifySnapshotOwnership(userId: string, snapshotId: string): Promise<boolean>;
  retrieveMemory(
    userId: string,
    snapshotId: string,
    question: string,
    embedding: number[],
  ): Promise<EvidenceItem[]>;
  findResult(requestId: string): Promise<{ status: string } | null>;
  claimCall(requestId: string): Promise<boolean>;
  insertPending(row: PendingRow): Promise<void>;
  finalize(requestId: string, ownerId: string, patch: FinalPatch): Promise<void>;
};

export type PendingRow = {
  request_id: string;
  owner_id: string;
  snapshot_id: string;
  condition: Condition;
  question: string;
};

export type FinalPatch = {
  status: "success" | "failed";
  answer_text: string | null;
  failure_code: string | null;
  evidence_sha256: string | null;
  retrieval_ms: number | null;
  model_http_ms: number | null;
  gateway_ms: number | null;
  first_token_ms: null;
  input_tokens: number | null;
  output_tokens: number | null;
};

export type PilotDeps = {
  db: PilotDb;
  fetch: typeof fetch;
  env: Record<string, string | undefined>;
  now: () => number;
  digest: (value: string) => Promise<string>;
};

async function sha256Hex(value: string, digest: PilotDeps["digest"]): Promise<string> {
  return digest(value);
}

function withCors(response: Response, origin: string | null): Response {
  if (!origin) return response;
  const headers = new Headers(response.headers);
  for (const [key, value] of Object.entries(corsHeaders(origin))) {
    headers.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function jsonError(error: PilotValidationError, origin: string | null = null): Response {
  return withCors(
    new Response(JSON.stringify({ error: error.message }), {
      status: error.status,
      headers: { "content-type": "application/json" },
    }),
    origin,
  );
}

export async function handlePilotRequest(req: Request, deps: PilotDeps): Promise<Response> {
  const gatewayStarted = deps.now();
  const corsOrigin = allowedCorsOrigin(req, deps.env);
  if (req.method === "OPTIONS") {
    if (!corsOrigin) {
      return new Response(null, { status: 403 });
    }
    return new Response(null, {
      status: 204,
      headers: corsHeaders(corsOrigin),
    });
  }
  if (req.method !== "POST") {
    return jsonError(new PilotValidationError("POST required", 405), corsOrigin);
  }
  try {
    const token = bearerToken(req);
    if (!token) {
      throw new PilotValidationError("missing bearer token", 401);
    }
    const claims = decodeJwtPayload(token);
    // Reject anon/expired/malformed claims before any database RPC.
    assertApplicationUserJwt(claims, Math.floor(deps.now() / 1000));
    const contentLength = Number(req.headers.get("content-length") ?? "0");
    if (contentLength) {
      rejectOversized(contentLength, MAX_REQUEST_BYTES, "request");
    }
    const raw = new Uint8Array(await req.arrayBuffer());
    rejectOversized(raw.byteLength, MAX_REQUEST_BYTES, "request");
    const payload = JSON.parse(new TextDecoder().decode(raw)) as Record<string, unknown>;
    const body = parsePilotBody(payload);
    const session = await deps.db.sessionSettings();
    const allowlisted = await deps.db.accessIsActive(claims.sub ?? "");
    const userId = assertPilotAccess(
      claims,
      Math.floor(deps.now() / 1000),
      allowlisted,
      session !== null,
    );
    const existing = await deps.db.findResult(body.request_id);
    if (existing) {
      throw new PilotValidationError("duplicate request_id", 409);
    }
    const owned = await deps.db.verifySnapshotOwnership(userId, body.snapshot_id);
    if (!owned) {
      throw new PilotValidationError("snapshot not owned by caller", 403);
    }
    // Prepare fixed server settings and messages before any durable pending row.
    const config = readServerConfig(deps.env);
    let evidence: EvidenceItem[] = [];
    let retrievalMs: number | null = null;
    if (shouldRetrieve(body.condition)) {
      const retrievalStarted = deps.now();
      evidence = await deps.db.retrieveMemory(
        userId,
        body.snapshot_id,
        body.question,
        body.embedding ?? [],
      );
      retrievalMs = deps.now() - retrievalStarted;
    }
    const evidenceSha = await sha256Hex(evidenceCanonical(evidence), deps.digest);
    const messages = buildMessages(body.question, evidence);
    const modelPayload = buildModelPayload(body.condition, messages, config);
    const claimed = await deps.db.claimCall(body.request_id);
    if (!claimed) {
      throw new PilotValidationError("call rate exceeded", 429);
    }
    await deps.db.insertPending({
      request_id: body.request_id,
      owner_id: userId,
      snapshot_id: body.snapshot_id,
      condition: body.condition,
      question: body.question,
    });
    try {
      const model = await callModelOnce(config, modelPayload, deps.fetch, deps.now);
      await deps.db.finalize(body.request_id, userId, {
        status: "success",
        answer_text: model.text,
        failure_code: null,
        evidence_sha256: evidenceSha,
        retrieval_ms: retrievalMs,
        model_http_ms: model.httpMs,
        gateway_ms: deps.now() - gatewayStarted,
        first_token_ms: null,
        input_tokens: model.inputTokens,
        output_tokens: model.outputTokens,
      });
      return withCors(
        Response.json({
          request_id: body.request_id,
          status: "success",
          condition: body.condition,
          answer_text: model.text,
          retrieval_ms: retrievalMs,
          model_http_ms: model.httpMs,
          gateway_ms: deps.now() - gatewayStarted,
          first_token_ms: null,
          input_tokens: model.inputTokens,
          output_tokens: model.outputTokens,
          evidence_sha256: evidenceSha,
        }),
        corsOrigin,
      );
    } catch (error) {
      const failure = sanitizeFailure(
        error instanceof PilotValidationError ? error.message : "model_request_failed",
      );
      await deps.db.finalize(body.request_id, userId, {
        status: "failed",
        answer_text: null,
        failure_code: failure.failure_code,
        evidence_sha256: evidenceSha,
        retrieval_ms: retrievalMs,
        model_http_ms: null,
        gateway_ms: deps.now() - gatewayStarted,
        first_token_ms: null,
        input_tokens: null,
        output_tokens: null,
      });
      return jsonError(new PilotValidationError(failure.failure_code, 502), corsOrigin);
    }
  } catch (error) {
    if (error instanceof PilotValidationError) {
      return jsonError(error, corsOrigin);
    }
    return jsonError(new PilotValidationError("request failed", 400), corsOrigin);
  }
}
