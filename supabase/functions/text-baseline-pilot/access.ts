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

export function assertPilotAccess(
  claims: JwtClaims,
  nowEpochSeconds: number,
  allowlisted: boolean,
  sessionPresent: boolean,
): string {
  if (!claims.sub) {
    throw new PilotValidationError("JWT missing subject", 401);
  }
  if (typeof claims.exp !== "number" || claims.exp <= nowEpochSeconds) {
    throw new PilotValidationError("JWT expired", 401);
  }
  if (claims.role !== "authenticated") {
    throw new PilotValidationError("JWT is not an application-user token", 401);
  }
  if (!sessionPresent) {
    throw new PilotValidationError("pilot session configuration missing or expired", 403);
  }
  if (!allowlisted) {
    throw new PilotValidationError("caller is not on the supervised-pilot allowlist", 403);
  }
  return claims.sub;
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
