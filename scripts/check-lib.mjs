// Pure pieces of `npm run check` (see check.mjs): which steps run, and how the result reads.
// Core Node modules only.
import { join } from "node:path";
import { venvPython } from "./dev-lib.mjs";

/**
 * The ordered steps of the definition of green (CLAUDE.md §5): types, frontend tests, build,
 * the Rust shell, then the kernel suite. A step is `skip`ped only for a stated reason; the
 * summary says so, so a skipped step can never read as a pass.
 */
export function checkPlan({ root, platform = process.platform, python, pythonExists, cargoAvailable, skipCargo = false }) {
  const py = python || venvPython(root, platform);
  const steps = [
    { name: "tsc", cmd: "npx", args: ["--no-install", "tsc", "--noEmit"] },
    { name: "frontend tests", cmd: "npm", args: ["run", "test:fe"] },
    { name: "vite build", cmd: "npm", args: ["run", "build"] },
  ];
  if (skipCargo) {
    steps.push({ name: "cargo check", skip: "skipped with --skip-cargo" });
  } else if (!cargoAvailable) {
    steps.push({ name: "cargo check", skip: "cargo not found on PATH" });
  } else {
    steps.push({ name: "cargo check", cmd: "cargo", args: ["check", "--manifest-path", join(root, "src-tauri", "Cargo.toml")] });
  }
  if (pythonExists) {
    steps.push({ name: "pytest (kernel)", cmd: py, args: ["-m", "pytest", "KASANE", "-q", "-p", "no:cacheprovider"] });
  } else {
    steps.push({ name: "pytest (kernel)", fail: `Python not found at ${py}. Create the venv (see README) or set KOKYU_PYTHON.` });
  }
  return steps;
}

/** results: [{name, status: "pass"|"fail"|"skip", note?}] -> {lines, ok, skipped} */
export function summarize(results) {
  const icon = { pass: "PASS", fail: "FAIL", skip: "SKIP" };
  const lines = results.map((r) => `${icon[r.status]}  ${r.name}${r.note ? `  (${r.note})` : ""}`);
  const ok = results.every((r) => r.status !== "fail");
  const skipped = results.filter((r) => r.status === "skip").map((r) => r.name);
  lines.push("");
  lines.push(
    !ok
      ? "RED: fix the failing steps above."
      : skipped.length
        ? `GREEN, but not fully verified: skipped ${skipped.join(", ")}.`
        : "GREEN: every step passed.",
  );
  return { lines, ok, skipped };
}
