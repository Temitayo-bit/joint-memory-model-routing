import nodeAssert from "node:assert/strict";

function assertEquals(actual: unknown, expected: unknown): void {
  nodeAssert.deepEqual(actual, expected);
}

function assert(condition: unknown): asserts condition {
  if (!condition) throw new Error("assertion failed");
}
import { createPostgrestDb } from "./postgrest.ts";

Deno.test("PostgREST adapter uses the user JWT and publishable key, not the model bearer", async () => {
  const seen: string[] = [];
  const fetchImpl = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    seen.push(`${init?.method}:${url}`);
    const headers = new Headers(init?.headers);
    assertEquals(headers.get("authorization"), "Bearer user-jwt");
    assertEquals(headers.get("apikey"), "publishable-key");
    assertEquals(headers.get("authorization")?.includes("server-only-bearer"), false);
    if (url.includes("pilot_access_is_active")) {
      return Promise.resolve(new Response("true", { headers: { "content-type": "application/json" } }));
    }
    return Promise.resolve(new Response("[]", { headers: { "content-type": "application/json" } }));
  }) as typeof fetch;
  const db = createPostgrestDb({
    url: "https://example.supabase.co",
    anonKey: "publishable-key",
    jwt: "user-jwt",
    fetchImpl,
  });
  assertEquals(await db.accessIsActive("user"), true);
  assertEquals(await db.findResult("33333333-3333-4333-8333-333333333333"), null);
  assert(seen.every((row) => !row.includes("model.example")));
});

Deno.test("PostgREST adapter accepts empty successful write bodies", async () => {
  const fetchImpl = (() =>
    Promise.resolve(new Response("", { status: 201 }))) as typeof fetch;
  const db = createPostgrestDb({
    url: "https://example.supabase.co",
    anonKey: "publishable-key",
    jwt: "user-jwt",
    fetchImpl,
  });
  await db.insertPending({
    request_id: "33333333-3333-4333-8333-333333333333",
    owner_id: "11111111-1111-4111-8111-111111111111",
    snapshot_id: "22222222-2222-4222-8222-222222222222",
    condition: "S0",
    question: "q",
  });
});
