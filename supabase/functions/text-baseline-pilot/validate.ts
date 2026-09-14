import {
  ALLOWED_BODY_KEYS,
  ALLOWED_GENERATION_SEEDS,
  CONDITIONS,
  EMBEDDING_DIMS,
  MEMORY_CONDITIONS,
  NORM_TOLERANCE,
  REJECTED_CLIENT_KEYS,
  type Condition,
} from "./constants.ts";

export type PilotBody = {
  request_id: string;
  snapshot_id: string;
  question: string;
  condition: Condition;
  embedding?: number[];
  generation_seed?: number;
};

export class PilotValidationError extends Error {
  status: number;
  constructor(message: string, status = 400) {
    super(message);
    this.status = status;
  }
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function assertUuid(value: unknown, label: string): string {
  if (typeof value !== "string" || !UUID_RE.test(value)) {
    throw new PilotValidationError(`${label} must be a UUID`);
  }
  return value;
}

export function validateEmbedding(value: unknown): number[] {
  if (!Array.isArray(value) || value.length !== EMBEDDING_DIMS) {
    throw new PilotValidationError(`embedding must have ${EMBEDDING_DIMS} dimensions`);
  }
  const floats: number[] = [];
  let sumSquares = 0;
  for (const item of value) {
    if (typeof item !== "number" || !Number.isFinite(item)) {
      throw new PilotValidationError("embedding values must be finite numbers");
    }
    floats.push(item);
    sumSquares += item * item;
  }
  const norm = Math.sqrt(sumSquares);
  if (Math.abs(norm - 1) > NORM_TOLERANCE) {
    throw new PilotValidationError("embedding must be L2-normalized");
  }
  return floats;
}

export function validateGenerationSeed(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || !ALLOWED_GENERATION_SEEDS.has(value)) {
    throw new PilotValidationError("generation_seed must be one of 42, 43, or 44");
  }
  return value;
}

export function parsePilotBody(payload: Record<string, unknown>): PilotBody {
  for (const key of Object.keys(payload)) {
    if (!ALLOWED_BODY_KEYS.has(key) || REJECTED_CLIENT_KEYS.includes(key)) {
      throw new PilotValidationError(`unsupported field: ${key}`);
    }
  }
  const condition = payload.condition;
  if (typeof condition !== "string" || !(CONDITIONS as readonly string[]).includes(condition)) {
    throw new PilotValidationError("condition must be S0, S1, L0, or L1");
  }
  const typed = condition as Condition;
  if (typeof payload.question !== "string" || payload.question.trim().length === 0) {
    throw new PilotValidationError("question is required");
  }
  const body: PilotBody = {
    request_id: assertUuid(payload.request_id, "request_id"),
    snapshot_id: assertUuid(payload.snapshot_id, "snapshot_id"),
    question: payload.question,
    condition: typed,
  };
  if (payload.generation_seed !== undefined) {
    body.generation_seed = validateGenerationSeed(payload.generation_seed);
  }
  if (MEMORY_CONDITIONS.has(typed)) {
    body.embedding = validateEmbedding(payload.embedding);
  } else if (payload.embedding !== undefined) {
    throw new PilotValidationError("no-memory conditions must not include an embedding");
  }
  return body;
}

export function rejectOversized(bytes: number, max: number, label: string): void {
  if (bytes > max) {
    throw new PilotValidationError(`${label} exceeds size limit`, 413);
  }
}
