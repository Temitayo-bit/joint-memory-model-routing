import type { EvidenceItem } from "./prompt.ts";
import { RETRIEVAL_CONFIG } from "./constants.ts";

export function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`).join(",")}}`;
  }
  throw new Error("unhashable");
}

export function evidencePayload(evidence: EvidenceItem[]) {
  return {
    ...RETRIEVAL_CONFIG,
    items: evidence.map((item) => ({
      content: item.content,
      id: item.item_id,
      kind: item.item_kind,
    })),
  };
}

export function evidenceCanonical(evidence: EvidenceItem[]): string {
  return canonicalJson(evidencePayload(evidence));
}
