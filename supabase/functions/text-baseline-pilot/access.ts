import type { ServerConfig } from "./constants.ts";
import { PilotValidationError } from "./validate.ts";

export type JwtClaims = {
  sub?: string;
  exp?: number;
  role?: string;
};

export function bearerToken(req: Request): string | null {
  const header = req.headers.get("Authorization") ?? req.headers.get("authorization");
  if (!header) return null;
  const match = /^Bearer\s+(\S+)/i.exec(header);
  return match ? match[1] : null;
}

export function decodeJwtPayload(token: string): JwtClaims {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new PilotValidationError("malformed JWT", 401);
  }
  const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
  try {
    const json = atob(padded);
    return JSON.parse(json) as JwtClaims;
  } catch {
    throw new PilotValidationError("malformed JWT", 401);
  }
}

/** Validate application-user JWT claims locally before any database call. */
export function assertApplicationUserJwt(claims: JwtClaims, nowEpochSeconds: number): string {
  if (!claims.sub) {
    throw new PilotValidationError("JWT missing subject", 401);
  }
  if (typeof claims.exp !== "number" || claims.exp <= nowEpochSeconds) {
    throw new PilotValidationError("JWT expired", 401);
  }
  if (claims.role !== "authenticated") {
    throw new PilotValidationError("JWT is not an application-user token", 401);
  }
  return claims.sub;
}

export function assertPilotAccess(
  claims: JwtClaims,
  nowEpochSeconds: number,
  allowlisted: boolean,
  sessionPresent: boolean,
): string {
  const userId = assertApplicationUserJwt(claims, nowEpochSeconds);
  if (!sessionPresent) {
    throw new PilotValidationError("pilot session configuration missing or expired", 403);
  }
  if (!allowlisted) {
    throw new PilotValidationError("caller is not on the supervised-pilot allowlist", 403);
  }
  return userId;
}

export function readServerConfig(env: Record<string, string | undefined>): ServerConfig {
  const required: Array<keyof ServerConfig> = [
    "modelBaseUrl",
    "modelBearer",
    "smallModelId",
    "largeModelId",
    "smallRevision",
    "largeRevision",
    "smallQuantization",
    "largeQuantization",
  ];
  const mapped: Record<string, string | undefined> = {
    modelBaseUrl: env.PILOT_MODEL_BASE_URL,
    modelBearer: env.PILOT_MODEL_BEARER,
    smallModelId: env.PILOT_SMALL_MODEL_ID,
    largeModelId: env.PILOT_LARGE_MODEL_ID,
    smallRevision: env.PILOT_SMALL_MODEL_REVISION,
    largeRevision: env.PILOT_LARGE_MODEL_REVISION,
    smallQuantization: env.PILOT_SMALL_QUANTIZATION,
    largeQuantization: env.PILOT_LARGE_QUANTIZATION,
  };
  for (const key of required) {
    if (!mapped[key]) {
      throw new PilotValidationError("server model configuration is incomplete", 503);
    }
  }
  return mapped as ServerConfig;
}

/** Browser CORS allowlist from PILOT_CORS_ORIGINS (comma-separated exact origins). */
export function allowedCorsOrigin(
  req: Request,
  env: Record<string, string | undefined>,
): string | null {
  const origin = req.headers.get("Origin");
  if (!origin) return null;
  const configured = (env.PILOT_CORS_ORIGINS ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  return configured.includes(origin) ? origin : null;
}

export function corsHeaders(origin: string | null): Record<string, string> {
  if (!origin) return {};
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-headers": "authorization, content-type, apikey, x-client-info",
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-max-age": "86400",
    vary: "Origin",
  };
}
