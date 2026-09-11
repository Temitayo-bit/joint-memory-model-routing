import { MEMORY_CONDITIONS, type Condition } from "./constants.ts";

export const SYSTEM_PROMPT =
  "Answer the question. If memory evidence is listed, you may use those facts and source passages. If no memory evidence is listed, answer from general knowledge and do not invent private lab facts.";

export type EvidenceItem = {
  item_id: string;
  item_kind: string;
  content: string;
};

export function buildMessages(question: string, evidence: EvidenceItem[]): Array<{ role: string; content: string }> {
  const lines: string[] = [];
  if (evidence.length > 0) {
    lines.push("Memory evidence:");
    for (const item of evidence) {
      lines.push(`- [${item.item_kind}] ${item.content}`);
    }
    lines.push("");
  } else {
    lines.push("Memory evidence: none");
    lines.push("");
  }
  lines.push("Question:");
  lines.push(question);
  return [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: lines.join("\n") },
  ];
}

export function shouldRetrieve(condition: Condition): boolean {
  return MEMORY_CONDITIONS.has(condition);
}

export function sanitizeFailure(code: string): { status: "failed"; failure_code: string; answer_text: null } {
  return { status: "failed", failure_code: code, answer_text: null };
}
