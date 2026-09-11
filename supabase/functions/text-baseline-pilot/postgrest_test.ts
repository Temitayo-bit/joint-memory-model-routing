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
