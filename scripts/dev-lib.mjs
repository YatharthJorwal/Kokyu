// Small, testable pieces of `npm run dev` (see dev.mjs). Core Node modules only.
import { posix, win32 } from "node:path";

/** The venv's Python for this platform, matching what the Tauri shell uses. */
export function venvPython(root, platform = process.platform) {
  // Join with the target platform's separator, not the host's, so a plan for
  // another platform reads the way it would there (and tests agree on any host).
  return platform === "win32"
    ? win32.join(root, ".venv", "Scripts", "python.exe")
    : posix.join(root, ".venv", "bin", "python");
}

/**
 * Splits streamed output into whole lines. Output arrives in arbitrary chunks, so a line can
 * span two of them; call `flush()` at the end to emit a final line that has no newline.
 */
export function lineSplitter(onLine) {
  let buffer = "";
  return {
    push(chunk) {
      buffer += chunk;
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        onLine(buffer.slice(0, index).replace(/\r$/, ""));
        buffer = buffer.slice(index + 1);
      }
    },
    flush() {
      if (buffer) onLine(buffer.replace(/\r$/, ""));
      buffer = "";
    },
  };
}

/** What `npm run dev` should do about the backend, given what it found. */
export function backendPlan({ alreadyRunning, pythonExists }) {
  if (alreadyRunning) return "reuse";
  if (!pythonExists) return "skip";
  return "start";
}
