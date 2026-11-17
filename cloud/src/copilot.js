// RAGY Copilot — RAG over project docs + OpenRouter (gemma-4-31b-it:free).
// Key comes from the Workers Secret OPENROUTER_API_KEY. Never in code/git.
// Fail-closed: no key or no question → explicit error, no fabricated answer.

import PROJECT_CONTEXT from "./context-embedded.js";

export const COPILOT_MODEL = "google/gemma-4-31b-it:free";

function systemPrompt() {
  return [
    "You are RAGY Copilot — the assistant of RAGY Cloud, an Arabic-first automation platform.",
    "Answer in the language of the question (Arabic or English). Be direct, honest, and evidence-based.",
    "Use ONLY the project context below when talking about RAGY's state. Never invent metrics or claims.",
    "If the context does not contain the answer, say so plainly instead of guessing.",
    "You can ask the caller to run a tool by replying with a line exactly like: TOOL: <tool_name> {json args}",
    "Available tools: list_tasks, list_automations, list_commands, verify_audit, post_command, create_task.",
    "--- RAGY PROJECT CONTEXT ---",
    PROJECT_CONTEXT,
  ].join("\n");
}

export async function askCopilot(question, env) {
  const key = (env.OPENROUTER_API_KEY || "").trim();
  if (!key) throw new Error("OPENROUTER_API_KEY secret is not configured on this Worker");
  const q = String(question || "").trim();
  if (!q) throw new Error("question is required");

  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${key}`,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://ragy-cloud-engine.aragy76.workers.dev",
      "X-Title": "RAGY Cloud Copilot",
    },
    body: JSON.stringify({
      model: COPILOT_MODEL,
      messages: [
        { role: "system", content: systemPrompt() },
        { role: "user", content: q },
      ],
      max_tokens: 900,
      temperature: 0.3,
    }),
  });

  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    throw new Error(`OpenRouter HTTP ${response.status}: ${detail}`);
  }
  const data = await response.json();
  const answer = data?.choices?.[0]?.message?.content || "";
  if (!answer) throw new Error("empty answer from model");

  // parse an optional tool instruction line
  let tool = null;
  const match = answer.match(/TOOL:\s*([a-z_]+)\s*(\{.*\})?\s*$/m);
  if (match) {
    try {
      tool = { name: match[1], args: match[2] ? JSON.parse(match[2]) : {} };
    } catch { tool = null; }
  }
  return {
    answer: answer.replace(/TOOL:\s*[^\n]*/g, "").trim(),
    tool,
    model: COPILOT_MODEL,
    usage: data?.usage || null,
  };
}
