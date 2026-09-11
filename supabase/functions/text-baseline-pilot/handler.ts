import { evidenceCanonical } from "./evidence.ts";
import { MAX_REQUEST_BYTES, type Condition } from "./constants.ts";
import { assertPilotAccess, bearerToken, decodeJwtPayload, readServerConfig } from "./access.ts";
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
  countRecentCalls(userId: string, windowSeconds: number, nowMs: number): Promise<number>;
  recordCall(userId: string, requestId: string, nowMs: number): Promise<void>;
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

function jsonError(error: PilotValidationError): Response {
  return new Response(JSON.stringify({ error: error.message }), {
    status: error.status,
    headers: { "content-type": "application/json" },
  });
}

export async function handlePilotRequest(req: Request, deps: PilotDeps): Promise<Response> {
  const gatewayStarted = deps.now();
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }
  if (req.method !== "POST") {
    return jsonError(new PilotValidationError("POST required", 405));
  }
  try {
    const token = bearerToken(req);
    if (!token) {
      throw new PilotValidationError("missing bearer token", 401);
    }
    const claims = decodeJwtPayload(token);
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
    const recent = await deps.db.countRecentCalls(userId, session!.window_seconds, deps.now());
    if (recent >= session!.max_calls) {
      throw new PilotValidationError("call rate exceeded", 429);
    }
    const owned = await deps.db.verifySnapshotOwnership(userId, body.snapshot_id);
    if (!owned) {
      throw new PilotValidationError("snapshot not owned by caller", 403);
    }
    await deps.db.recordCall(userId, body.request_id, deps.now());
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
    await deps.db.insertPending({
      request_id: body.request_id,
      owner_id: userId,
      snapshot_id: body.snapshot_id,
      condition: body.condition,
      question: body.question,
    });
    const config = readServerConfig(deps.env);
    const messages = buildMessages(body.question, evidence);
    try {
      const model = await callModelOnce(
        config,
        buildModelPayload(body.condition, messages, config),
        deps.fetch,
        deps.now,
      );
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
      return Response.json({
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
      });
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
      return jsonError(new PilotValidationError(failure.failure_code, 502));
    }
  } catch (error) {
    if (error instanceof PilotValidationError) {
      return jsonError(error);
    }
    return jsonError(new PilotValidationError("request failed", 400));
  }
}
