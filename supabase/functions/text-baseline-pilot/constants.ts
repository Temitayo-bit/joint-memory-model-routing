export const CONDITIONS = ["S0", "S1", "L0", "L1"] as const;
export type Condition = typeof CONDITIONS[number];

export const MEMORY_CONDITIONS = new Set<Condition>(["S1", "L1"]);
export const EMBEDDING_DIMS = 384;
export const NORM_TOLERANCE = 1e-3;
export const MAX_REQUEST_BYTES = 16 * 1024;
export const MAX_MODEL_RESPONSE_BYTES = 64 * 1024;
export const ALLOWED_BODY_KEYS = new Set([
  "request_id",
  "snapshot_id",
  "question",
  "condition",
  "embedding",
]);
export const REJECTED_CLIENT_KEYS = [
  "model_url",
  "base_url",
  "model",
  "model_id",
  "temperature",
  "top_p",
  "top_k",
  "min_p",
  "seed",
  "max_tokens",
  "prompt",
  "messages",
  "owner_id",
  "reference_answer",
  "expected_answer",
  "bearer",
  "authorization",
  "revision",
  "quantization",
];

export const FIXED_GENERATION = Object.freeze({
  stream: false,
  max_tokens: 256,
  temperature: 0.7,
  top_p: 0.8,
  top_k: 20,
  min_p: 0,
  seed: 42,
  chat_template_kwargs: Object.freeze({ enable_thinking: false }),
});

export const UPSTREAM_TIMEOUT_MS = 70_000;

export type ServerConfig = {
  modelBaseUrl: string;
  modelBearer: string;
  smallModelId: string;
  largeModelId: string;
  smallRevision: string;
  largeRevision: string;
  smallQuantization: string;
  largeQuantization: string;
};

export function modelAlias(condition: Condition): "small" | "large" {
  return condition.startsWith("L") ? "large" : "small";
}
