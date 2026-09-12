import nodeAssert from "node:assert/strict";

function assertEquals(actual: unknown, expected: unknown): void {
  nodeAssert.deepEqual(actual, expected);
}

async function assertRejects(fn: () => Promise<unknown>): Promise<void> {
  let failed = false;
  try {
    await fn();
  } catch {
    failed = true;
  }
  nodeAssert.equal(failed, true);
}

function assert(condition: unknown): asserts condition {
  if (!condition) throw new Error("assertion failed");
}
import { assertApplicationUserJwt, assertPilotAccess, decodeJwtPayload, readServerConfig } from "./access.ts";
import { FIXED_GENERATION } from "./constants.ts";
import { evidenceCanonical } from "./evidence.ts";
import { handlePilotRequest, type PilotDb, type PilotDeps, type SessionSettings } from "./handler.ts";
import { buildModelPayload, callModelOnce } from "./model_client.ts";
import { PilotValidationError, parsePilotBody, validateEmbedding } from "./validate.ts";

function encodeJwt(claims: Record<string, unknown>): string {
  const encode = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
  return `${encode({ alg: "none", typ: "JWT" })}.${encode(claims)}.sig`;
}

function unitEmbedding(): number[] {
  const values = Array.from({ length: 384 }, () => 0);
  values[0] = 1;
  return values;
}

const USER = "11111111-1111-4111-8111-111111111111";
const SNAP = "22222222-2222-4222-8222-222222222222";
const REQ = "33333333-3333-4333-8333-333333333333";
const REQ2 = "44444444-4444-4444-8444-444444444444";

function futureClaims(overrides: Record<string, unknown> = {}) {
  return { sub: USER, exp: 4_000_000_000, role: "authenticated", ...overrides };
}

const TEST_ENV = {
  PILOT_MODEL_BASE_URL: "https://model.example.invalid",
  PILOT_MODEL_BEARER: "server-only-bearer",
  PILOT_SMALL_MODEL_ID: "small-alias",
  PILOT_LARGE_MODEL_ID: "large-alias",
  PILOT_SMALL_MODEL_REVISION: "unverified-revision",
  PILOT_LARGE_MODEL_REVISION: "unverified-revision",
  PILOT_SMALL_QUANTIZATION: "unverified-quant",
  PILOT_LARGE_QUANTIZATION: "unverified-quant",
  PILOT_CORS_ORIGINS: "https://app.example",
};

class MemoryDb implements PilotDb {
  allow = new Set<string>([USER]);
  session: SessionSettings | null = { deadline: "2099-01-01T00:00:00Z", max_calls: 6, window_seconds: 60 };
  owners = new Map<string, string>([[SNAP, USER]]);
  results = new Map<string, { status: string }>();
  calls: Array<{ userId: string; requestId: string; at: number }> = [];
  retrieveCount = 0;
  events: string[] = [];
  pendingCount = 0;
  claimAlways = true;
  sessionLookups = 0;
  allowlistLookups = 0;

  accessIsActive(userId: string) {
    this.allowlistLookups += 1;
    this.events.push("allowlist");
    return Promise.resolve(this.allow.has(userId));
  }
  sessionSettings() {
    this.sessionLookups += 1;
    this.events.push("session");
    return Promise.resolve(this.session);
  }
  verifySnapshotOwnership(userId: string, snapshotId: string) {
    return Promise.resolve(this.owners.get(snapshotId) === userId);
  }
  retrieveMemory() {
    this.retrieveCount += 1;
    this.events.push("retrieve");
    return Promise.resolve([
      { item_id: "M01", item_kind: "fact", content: "The Northriver Lab preferred tea is jasmine green tea." },
    ]);
  }
  findResult(requestId: string) {
    return Promise.resolve(this.results.get(requestId) ?? null);
  }
  claimCall(requestId: string) {
    const nowMs = 1_700_000_000_000;
    const windowSeconds = this.session?.window_seconds ?? 60;
    const maxCalls = this.session?.max_calls ?? 0;
    const cutoff = nowMs - windowSeconds * 1000;
    const recent = this.calls.filter((row) => row.at >= cutoff).length;
    if (!this.claimAlways || recent >= maxCalls || this.calls.some((row) => row.requestId === requestId)) {
      return Promise.resolve(false);
    }
    this.calls.push({ userId: USER, requestId, at: nowMs });
    this.events.push("claim");
    return Promise.resolve(true);
  }
  insertPending(row: { request_id: string }) {
    this.pendingCount += 1;
    this.events.push("pending");
    this.results.set(row.request_id, { status: "pending" });
    return Promise.resolve();
  }
  finalize(requestId: string, _ownerId: string, patch: { status: "success" | "failed"; failure_code: string | null }) {
    this.events.push("finalize:" + patch.status);
    this.results.set(requestId, { status: patch.status });
    this.lastFailure = patch.failure_code;
    return Promise.resolve();
  }
  lastFailure: string | null = null;
}

function deps(db: MemoryDb, fetchImpl: typeof fetch): PilotDeps {
  let clock = 1_700_000_000_000;
  return {
    db,
    fetch: fetchImpl,
    env: TEST_ENV,
    now: () => {
      clock += 1;
      return clock;
    },
    digest: (value) => Promise.resolve(`hash:${value.length}`),
  };
}

function requestFor(
  condition: string,
  extra: Record<string, unknown> = {},
  headers: Record<string, string> = {},
  requestId = REQ,
): Request {
  const body: Record<string, unknown> = {
    request_id: requestId,
    snapshot_id: SNAP,
    question: "What tea does the Northriver Lab prefer?",
    condition,
    ...extra,
  };
  if (condition === "S1" || condition === "L1") {
    body.embedding = extra.embedding ?? unitEmbedding();
  }
  return new Request("http://localhost/text-baseline-pilot", {
    method: "POST",
    headers: {
      authorization: `Bearer ${encodeJwt(futureClaims())}`,
      "content-type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

function okFetch(): typeof fetch {
  return ((_input, init) => {
    const payload = JSON.parse(String(init?.body)) as Record<string, unknown>;
    assertEquals(payload.stream, false);
    assertEquals(payload.max_tokens, 256);
    assertEquals(payload.temperature, 0.7);
    assertEquals(payload.top_p, 0.8);
    assertEquals(payload.top_k, 20);
    assertEquals(payload.min_p, 0);
    assertEquals(payload.seed, 42);
    assertEquals(payload.chat_template_kwargs, { enable_thinking: false });
    assertEquals((init as RequestInit).redirect, "error");
    return Promise.resolve(
      Response.json({
        choices: [{ message: { content: "jasmine green tea" } }],
        usage: { prompt_tokens: 11, completion_tokens: 5 },
      }),
    );
  }) as typeof fetch;
}

Deno.test("evidence canonical JSON matches the Python harness shape", () => {
  const encoded = evidenceCanonical([
    { item_id: "M01", item_kind: "fact", content: "hello" },
  ]);
  assertEquals(
    encoded,
    '{"combined":"lexical_rank_plus_vector_similarity","idf":"ln((N+1)/(df+1))+1","items":[{"content":"hello","id":"M01","kind":"fact"}],"lexical":"snapshot_idf_token_overlap","limit":4,"limit_cap":8,"not_semantic_retrieval":true,"retriever":"pilot_hybrid_v2_1","stopword_count":127,"stopword_source":"https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/src/backend/snowball/stopwords/english.stop","stopwords":"postgresql_17_english_snowball","token_pattern":"[A-Za-z0-9]+","vector":"cosine_similarity_1_minus_distance"}',
  );
});

Deno.test("JWT missing is rejected", async () => {
  const db = new MemoryDb();
  const req = new Request("http://localhost/text-baseline-pilot", {
    method: "POST",
    body: JSON.stringify({
      request_id: REQ,
      snapshot_id: SNAP,
      question: "q",
      condition: "S0",
    }),
  });
  const res = await handlePilotRequest(req, deps(db, okFetch()));
  assertEquals(res.status, 401);
});

Deno.test("allowlist rejection", async () => {
  const db = new MemoryDb();
  db.allow.clear();
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 403);
});

Deno.test("application-user role is required before database calls", async () => {
  const db = new MemoryDb();
  const req = new Request("http://localhost/text-baseline-pilot", {
    method: "POST",
    headers: { authorization: `Bearer ${encodeJwt(futureClaims({ role: "anon" }))}` },
    body: JSON.stringify({
      request_id: REQ,
      snapshot_id: SNAP,
      question: "q",
      condition: "S0",
    }),
  });
  const res = await handlePilotRequest(req, deps(db, okFetch()));
  assertEquals(res.status, 401);
  assertEquals(db.sessionLookups, 0);
  assertEquals(db.allowlistLookups, 0);
});

Deno.test("CORS preflight and responses include configured origin", async () => {
  const db = new MemoryDb();
  const preflight = new Request("http://localhost/text-baseline-pilot", {
    method: "OPTIONS",
    headers: { origin: "https://app.example" },
  });
  const optionsRes = await handlePilotRequest(preflight, deps(db, okFetch()));
  assertEquals(optionsRes.status, 204);
  assertEquals(optionsRes.headers.get("access-control-allow-origin"), "https://app.example");
  assertEquals(optionsRes.headers.get("access-control-allow-headers")?.includes("authorization"), true);

  const denied = await handlePilotRequest(
    new Request("http://localhost/text-baseline-pilot", {
      method: "OPTIONS",
      headers: { origin: "https://evil.example" },
    }),
    deps(db, okFetch()),
  );
  assertEquals(denied.status, 403);

  const res = await handlePilotRequest(
    requestFor("S0", {}, { origin: "https://app.example" }),
    deps(db, okFetch()),
  );
  assertEquals(res.status, 200);
  assertEquals(res.headers.get("access-control-allow-origin"), "https://app.example");
});

Deno.test("expired JWT rejected", async () => {
  const db = new MemoryDb();
  const req = new Request("http://localhost/text-baseline-pilot", {
    method: "POST",
    headers: { authorization: `Bearer ${encodeJwt(futureClaims({ exp: 1 }))}` },
    body: JSON.stringify({
      request_id: REQ,
      snapshot_id: SNAP,
      question: "q",
      condition: "S0",
    }),
  });
  const res = await handlePilotRequest(req, deps(db, okFetch()));
  assertEquals(res.status, 401);
});

Deno.test("missing session configuration rejected", async () => {
  const db = new MemoryDb();
  db.session = null;
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 403);
});

Deno.test("malformed condition and embedding rejected", () => {
  let threw = false;
  try {
    parsePilotBody({
      request_id: REQ,
      snapshot_id: SNAP,
      question: "q",
      condition: "XL",
    });
  } catch {
    threw = true;
  }
  assert(threw);
  threw = false;
  try {
    validateEmbedding([0.1, 0.2]);
  } catch {
    threw = true;
  }
  assert(threw);
});

Deno.test("snapshot ownership is required", async () => {
  const db = new MemoryDb();
  db.owners.clear();
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 403);
  assertEquals(db.retrieveCount, 0);
  assertEquals(db.calls.length, 0);
});

Deno.test("no-memory conditions do not retrieve content", async () => {
  const db = new MemoryDb();
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 200);
  assertEquals(db.retrieveCount, 0);
  const json = await res.json();
  assertEquals(json.first_token_ms, null);
  assertEquals(json.input_tokens, 11);
});

Deno.test("memory conditions retrieve once before the model call", async () => {
  const db = new MemoryDb();
  const res = await handlePilotRequest(requestFor("S1"), deps(db, okFetch()));
  assertEquals(res.status, 200);
  assertEquals(db.retrieveCount, 1);
  assertEquals(db.events[0], "session");
  assertEquals(db.events[1], "allowlist");
  assertEquals(db.events[2], "retrieve");
  assertEquals(db.events[3], "claim");
  assertEquals(db.events[4], "pending");
});

Deno.test("duplicate request_id rejected", async () => {
  const db = new MemoryDb();
  db.results.set(REQ, { status: "pending" });
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 409);
});

Deno.test("throttled calls rejected", async () => {
  const db = new MemoryDb();
  db.session = { deadline: "2099-01-01T00:00:00Z", max_calls: 1, window_seconds: 60 };
  db.calls.push({ userId: USER, requestId: "prior", at: 1_700_000_000_000 });
  const res = await handlePilotRequest(requestFor("S0"), deps(db, okFetch()));
  assertEquals(res.status, 429);
});

Deno.test("client secrets and settings are rejected", () => {
  let threw = false;
  try {
    parsePilotBody({
      request_id: REQ,
      snapshot_id: SNAP,
      question: "q",
      condition: "S0",
      model_url: "https://evil.example",
    });
  } catch {
    threw = true;
  }
  assert(threw);
  const cfg = readServerConfig(TEST_ENV);
  assertEquals(cfg.modelBearer, "server-only-bearer");
  assertEquals(cfg.smallModelId, "small-alias");
});

Deno.test("redirects are rejected", async () => {
  const db = new MemoryDb();
  const fetchImpl = (() => Promise.reject(new TypeError("redirect"))) as typeof fetch;
  const res = await handlePilotRequest(requestFor("S0"), deps(db, fetchImpl));
  assertEquals(res.status, 502);
  assertEquals(db.lastFailure, "model redirect rejected");
  assert(!JSON.stringify(db).includes("upstream-secret"));
});

Deno.test("response size limit", async () => {
  const db = new MemoryDb();
  const fetchImpl = (() =>
    Promise.resolve(
      new Response("x".repeat(70 * 1024), { headers: { "content-length": String(70 * 1024) } }),
    )) as typeof fetch;
  const res = await handlePilotRequest(requestFor("S0"), deps(db, fetchImpl));
  assertEquals(res.status, 502);
});

Deno.test("fixed non-thinking generation settings", () => {
  const payload = buildModelPayload("L1", [{ role: "user", content: "q" }], readServerConfig(TEST_ENV));
  assertEquals(payload.model, "large-alias");
  assertEquals(payload.max_tokens, FIXED_GENERATION.max_tokens);
  assertEquals(payload.temperature, FIXED_GENERATION.temperature);
  assertEquals(payload.top_p, FIXED_GENERATION.top_p);
  assertEquals(payload.top_k, FIXED_GENERATION.top_k);
  assertEquals(payload.min_p, FIXED_GENERATION.min_p);
  assertEquals(payload.seed, FIXED_GENERATION.seed);
  assertEquals(payload.stream, false);
  assertEquals(payload.chat_template_kwargs, { enable_thinking: false });
});

Deno.test("decodeJwtPayload rejects malformed tokens", () => {
  let threw = false;
  try {
    decodeJwtPayload("not-a-jwt");
  } catch {
    threw = true;
  }
  assert(threw);
});

Deno.test("assertPilotAccess requires session and allowlist", () => {
  let threw = false;
  try {
    assertPilotAccess({ sub: USER, exp: 4_000_000_000, role: "authenticated" }, 10, true, false);
  } catch (error) {
    threw = error instanceof PilotValidationError;
  }
  assert(threw);
  threw = false;
  try {
    assertApplicationUserJwt({ sub: USER, exp: 4_000_000_000, role: "anon" }, 10);
  } catch (error) {
    threw = error instanceof PilotValidationError && error.status === 401;
  }
  assert(threw);
});

Deno.test("callModelOnce does not retry", async () => {
  let calls = 0;
  const fetchImpl = (() => {
    calls += 1;
    return Promise.reject(new Error("fail"));
  }) as typeof fetch;
  await assertRejects(() =>
    callModelOnce(readServerConfig(TEST_ENV), { model: "small-alias" }, fetchImpl, () => 1)
  );
  assertEquals(calls, 1);
});

Deno.test("pending is stored before a billed request", async () => {
  const db = new MemoryDb();
  const order: string[] = [];
  const fetchImpl = ((input: RequestInfo | URL, init?: RequestInit) => {
    order.push("fetch");
    return okFetch()(input, init);
  }) as typeof fetch;
  const wrapped = deps(db, fetchImpl);
  const originalInsert = db.insertPending.bind(db);
  db.insertPending = (row) => {
    order.push("pending");
    return originalInsert(row);
  };
  const res = await handlePilotRequest(requestFor("L0", {}, {}, REQ2), wrapped);
  assertEquals(res.status, 200);
  assertEquals(order[0], "pending");
  assertEquals(order[1], "fetch");
});
