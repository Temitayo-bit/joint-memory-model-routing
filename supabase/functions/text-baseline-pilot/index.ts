import { bearerToken } from "./access.ts";
import { handlePilotRequest } from "./handler.ts";
import { createPostgrestDb } from "./postgrest.ts";
import { productionDeps } from "./server.ts";

/**
 * Prepared Edge Function entry. Platform `verify_jwt` stays enabled in config.toml.
 * The caller's JWT is forwarded to PostgREST so RLS and SECURITY INVOKER RPCs apply
 * (same trust model as withSupabase({ auth: 'user' }), without importing that npm
 * package into this undeployed tree). Not deployed by this change.
 */
Deno.serve((req) => {
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
  const jwt = bearerToken(req) ?? "";
  const db = createPostgrestDb({
    url,
    anonKey,
    jwt,
    fetchImpl: fetch,
  });
  return handlePilotRequest(req, productionDeps(db));
});
