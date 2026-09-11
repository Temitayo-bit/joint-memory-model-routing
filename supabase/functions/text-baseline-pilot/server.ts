import { handlePilotRequest, type PilotDb, type PilotDeps } from "./handler.ts";
import type { EvidenceItem } from "./prompt.ts";
import type { SessionSettings } from "./handler.ts";

export async function defaultDigest(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join("");
}

export function envFromDeno(): Record<string, string | undefined> {
  return {
    PILOT_MODEL_BASE_URL: Deno.env.get("PILOT_MODEL_BASE_URL"),
    PILOT_MODEL_BEARER: Deno.env.get("PILOT_MODEL_BEARER"),
    PILOT_SMALL_MODEL_ID: Deno.env.get("PILOT_SMALL_MODEL_ID"),
    PILOT_LARGE_MODEL_ID: Deno.env.get("PILOT_LARGE_MODEL_ID"),
    PILOT_SMALL_MODEL_REVISION: Deno.env.get("PILOT_SMALL_MODEL_REVISION"),
    PILOT_LARGE_MODEL_REVISION: Deno.env.get("PILOT_LARGE_MODEL_REVISION"),
    PILOT_SMALL_QUANTIZATION: Deno.env.get("PILOT_SMALL_QUANTIZATION"),
    PILOT_LARGE_QUANTIZATION: Deno.env.get("PILOT_LARGE_QUANTIZATION"),
  };
}

/** Production entry uses platform verify_jwt; this file does not import npm packages. */
export function productionDeps(db: PilotDb, fetchImpl: typeof fetch = fetch): PilotDeps {
  return {
    db,
    fetch: fetchImpl,
    env: envFromDeno(),
    now: () => Date.now(),
    digest: defaultDigest,
  };
}

export async function servePilot(req: Request, db: PilotDb): Promise<Response> {
  return await handlePilotRequest(req, productionDeps(db));
}

export type { EvidenceItem, SessionSettings };
