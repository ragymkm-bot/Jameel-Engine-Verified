// RAGY Copilot — RAG over project docs + OpenRouter free models.
// Key from Workers Secret OPENROUTER_API_KEY. Never in code/git.
// Fail-closed: no key or no question → explicit error, no fabricated answer.
// Resilient: bounded fallback chain when a provider is rate-limited.

import PROJECT_CONTEXT from "./context-embedded.js";

export const COPILOT_MODELS = [
  "inclusionai/ling-3.2-flash:free",
  "google/gemma-4-31b-it:free",
  "liquid/lfm-3-1.7b:free",
  "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "baidu/ernie-5.5-flash-preview:free",
];
export const COPILOT_MODEL = COPILOT_MODELS[0];

function systemPrompt() {
  return [
    "You are RAGY Copilot — the assistant of RAGY Cloud, an Arabic-first automation platform.",
    "Answer in the language of the question (Arabic or English). Be direct, honest, and evidence-based.",
    "MCP always means Model Context Protocol — NEVER 'Multi-Command Protocol' or any other expansion.",
    "Use ONLY the project context below when talking about RAGY's state. Never invent metrics or claims.",
    "If the context does not contain the answer, say so plainly instead of guessing.",
    "You can ask the caller to run a tool by replying with a line exactly like: TOOL: <tool_name> {json args}",
    "Available tools: list_tasks, list_automations, list_commands, verify_audit, post_command, create_task.",
    "--- RAGY PROJECT CONTEXT ---",
    PROJECT_CONTEXT,
  ].join("\n");
}

function extractTool(answer) {
  const match = answer.match(/TOOL:\s*([a-z_]+)\s*(\{.*\})?\s*$/m);
  if (!match) return null;
  try {
    return { name: match[1], args: match[2] ? JSON.parse(match[2]) : {} };
  } catch {
    return null;
  }
}

export async function askCopilot(question, env, secretLookup = null) {
  let key = (env.OPENROUTER_API_KEY || "").trim();
  if (!key && secretLookup) key = (await secretLookup("OPENROUTER_API_KEY") || "").trim();
  if (!key) throw new Error("OPENROUTER_API_KEY secret is not configured on this Worker");
  const q = String(question || "").trim();
  if (!q) throw new Error("question is required");

  const errors = [];
  for (const model of COPILOT_MODELS) {
    let response;
    try {
      response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${key}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://ragy-cloud-engine.aragy76.workers.dev",
          "X-Title": "RAGY Cloud Copilot",
        },
        body: JSON.stringify({
          model,
          messages: [
            { role: "system", content: systemPrompt() },
            { role: "user", content: q },
          ],
          max_tokens: 900,
          temperature: 0.3,
        }),
      });
    } catch (error) {
      errors.push(`${model}: network ${String(error).slice(0, 100)}`);
      continue;
    }
    if (!response.ok) {
      errors.push(`${model}: HTTP ${response.status}`);
      if (response.status === 429 || response.status === 503 || response.status >= 500) continue;
      throw new Error(`OpenRouter HTTP ${response.status} for ${model}`);
    }
    const data = await response.json();
    const answer = data?.choices?.[0]?.message?.content || "";
    if (!answer) {
      errors.push(`${model}: empty answer`);
      continue;
    }
    return {
      answer: answer.replace(/TOOL:\s*[^\n]*/g, "").trim(),
      tool: extractTool(answer),
      model,
      usage: data?.usage || null,
      fallback_count: errors.length,
    };
  }
  throw new Error(`all free models unavailable: ${errors.join(" | ").slice(0, 400)}`);
}
