/**
 * claude_query.mjs
 *
 * Thin wrapper around the Claude Agent SDK TypeScript.
 * Called by generator.py via subprocess.
 *
 * Usage: echo "<prompt>" | node claude_query.mjs
 *
 * - Reads the full prompt from stdin
 * - Calls Claude via the Agent SDK (uses ANTHROPIC_API_KEY from env)
 * - Writes the result text to stdout
 * - Writes errors to stderr and exits with code 1
 *
 * Tools are disabled — this is a pure text generation call.
 */

import { query } from "@anthropic-ai/claude-agent-sdk";

// Read prompt from stdin
const chunks = [];
for await (const chunk of process.stdin) {
  chunks.push(chunk);
}
const prompt = Buffer.concat(chunks).toString("utf-8").trim();

if (!prompt) {
  process.stderr.write("Error: empty prompt received on stdin\n");
  process.exit(1);
}

try {
  for await (const message of query({
    prompt,
    options: {
      tools: [],                          // no tools — pure text generation
      permissionMode: "bypassPermissions", // no interactive permission prompts
    },
  })) {
    if (message.type === "result") {
      if (message.subtype === "success") {
        process.stdout.write(message.result);
        process.exit(0);
      } else {
        // error_max_turns | error_during_execution | error_max_budget_usd | etc.
        const errors = message.errors ?? [];
        process.stderr.write(
          `Claude query failed (${message.subtype}):\n${errors.join("\n")}\n`
        );
        process.exit(1);
      }
    }
  }
} catch (err) {
  process.stderr.write(`Error: ${err.message}\n`);
  process.exit(1);
}
