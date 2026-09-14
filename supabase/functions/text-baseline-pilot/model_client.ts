import { FIXED_GENERATION, MAX_MODEL_RESPONSE_BYTES, UPSTREAM_TIMEOUT_MS, modelAlias, type Condition, type ServerConfig } from "./constants.ts";
import { PilotValidationError } from "./validate.ts";

export type ModelSuccess = {
  text: string;
  inputTokens: number | null;
  outputTokens: number | null;
  httpMs: number;
};

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, "")}${path}`;
}

function asNonNegativeInt(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

export function buildModelPayload(
  condition: Condition,
  messages: Array<{ role: string; content: string }>,
  config: ServerConfig,
  generationSeed?: number,
): Record<string, unknown> {
  const alias = modelAlias(condition);
  const model = alias === "large" ? config.largeModelId : config.smallModelId;
  return {
    model,
    messages,
    ...FIXED_GENERATION,
    ...(generationSeed === undefined ? {} : { seed: generationSeed }),
  };
}

export async function callModelOnce(
  config: ServerConfig,
  payload: Record<string, unknown>,
  fetchImpl: typeof fetch,
  now: () => number,
  timeoutMs: number = UPSTREAM_TIMEOUT_MS,
): Promise<ModelSuccess> {
  const started = now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetchImpl(joinUrl(config.modelBaseUrl, "/v1/chat/completions"), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${config.modelBearer}`,
      },
      body: JSON.stringify(payload),
      redirect: "error",
      signal: controller.signal,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "model_http_error";
    if (/abort/i.test(message) || (error instanceof DOMException && error.name === "AbortError")) {
      throw new PilotValidationError("model request timeout", 502);
    }
    if (/redirect/i.test(message)) {
      throw new PilotValidationError("model redirect rejected", 502);
    }
    throw new PilotValidationError("model request failed", 502);
  } finally {
    clearTimeout(timer);
  }
  if (response.status >= 300 && response.status < 400) {
    throw new PilotValidationError("model redirect rejected", 502);
  }
  const buffer = new Uint8Array(await readBounded(response, MAX_MODEL_RESPONSE_BYTES));
  const httpMs = now() - started;
  if (!response.ok) {
    throw new PilotValidationError("model request failed", 502);
  }
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(new TextDecoder().decode(buffer)) as Record<string, unknown>;
  } catch {
    throw new PilotValidationError("model response was not JSON", 502);
  }
  const choices = parsed.choices as Array<{ message?: { content?: string } }> | undefined;
  const text = choices?.[0]?.message?.content;
  if (typeof text !== "string" || text.length === 0) {
    throw new PilotValidationError("model response missing text", 502);
  }
  const usage = parsed.usage as { prompt_tokens?: unknown; completion_tokens?: unknown } | undefined;
  return {
    text,
    inputTokens: asNonNegativeInt(usage?.prompt_tokens),
    outputTokens: asNonNegativeInt(usage?.completion_tokens),
    httpMs,
  };
}

export async function readBounded(response: Response, maxBytes: number): Promise<ArrayBuffer> {
  const lengthHeader = response.headers.get("content-length");
  if (lengthHeader && Number(lengthHeader) > maxBytes) {
    throw new PilotValidationError("model response exceeds size limit", 502);
  }
  if (!response.body) {
    return new ArrayBuffer(0);
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    if (received > maxBytes) {
      await reader.cancel();
      throw new PilotValidationError("model response exceeds size limit", 502);
    }
    chunks.push(value);
  }
  const out = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out.buffer;
}
