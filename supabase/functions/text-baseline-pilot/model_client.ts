import { FIXED_GENERATION, MAX_MODEL_RESPONSE_BYTES, modelAlias, type Condition, type ServerConfig } from "./constants.ts";
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

export function buildModelPayload(
  condition: Condition,
  messages: Array<{ role: string; content: string }>,
  config: ServerConfig,
): Record<string, unknown> {
  const alias = modelAlias(condition);
  const model = alias === "large" ? config.largeModelId : config.smallModelId;
  return {
    model,
    messages,
    ...FIXED_GENERATION,
  };
}

export async function callModelOnce(
  config: ServerConfig,
  payload: Record<string, unknown>,
  fetchImpl: typeof fetch,
  now: () => number,
): Promise<ModelSuccess> {
  const started = now();
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
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "model_http_error";
    if (/redirect/i.test(message)) {
      throw new PilotValidationError("model redirect rejected", 502);
    }
    throw new PilotValidationError("model request failed", 502);
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
  const inputTokens = typeof usage?.prompt_tokens === "number" ? usage.prompt_tokens : null;
  const outputTokens = typeof usage?.completion_tokens === "number" ? usage.completion_tokens : null;
  return { text, inputTokens, outputTokens, httpMs };
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
