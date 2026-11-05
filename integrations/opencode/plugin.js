/**
 * OpenCode plugin for JESKO
 *
 * Install: Save as ~/.opencode/plugin/jesko.js (Linux/macOS)
 *          or %USERPROFILE%\.opencode\plugin\jesko.js (Windows)
 *
 * Events mapped:
 *   session.idle     -> task.completed
 *   session.error    -> task.failed
 *   permission.asked -> permission.required
 *
 * Ambiguous/unrecognized payloads are ignored.
 * This plugin does not mutate event or permission state.
 */

import { spawn } from "node:child_process";

function sendToJesko(payload) {
  const args = ["ingest", "--adapter", "opencode", "--stdin"];
  const child = spawn("jesko", args, { stdio: ["pipe", "ignore", "ignore"] });
  child.stdin.write(JSON.stringify(payload));
  child.stdin.end();
  // Non-blocking: we don't wait for jesko to complete
  child.unref();
}

export default function (opencode) {
  // Completion events
  opencode.on("session.idle", (session) => {
    sendToJesko({ type: "session.idle", session });
  });

  // Error/failure events
  opencode.on("session.error", (session, error) => {
    sendToJesko({ type: "session.error", session, error: String(error) });
  });

  // Permission request events
  opencode.on("permission.asked", (session, permission) => {
    sendToJesko({ type: "permission.asked", session, permission });
  });
}