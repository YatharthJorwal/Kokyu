// `npm run check`: the definition of green in one command (CLAUDE.md §5).
//   npm run check                 types, frontend tests, build, cargo check, kernel pytest
//   npm run check -- --skip-cargo skip the Rust step (no toolchain, or a quick loop)
// KOKYU_PYTHON overrides the Python used for pytest (default: .venv in the repo).
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checkPlan, summarize } from "./check-lib.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const shell = process.platform === "win32";

function onPath(cmd) {
  return spawnSync(cmd, ["--version"], { shell, stdio: "ignore" }).status === 0;
}

const python = process.env.KOKYU_PYTHON || undefined;
const plan = checkPlan({
  root,
  python,
  pythonExists: existsSync(python || checkPlan({ root, pythonExists: true, cargoAvailable: false }).at(-1).cmd),
  cargoAvailable: onPath("cargo"),
  skipCargo: process.argv.includes("--skip-cargo"),
});

const results = [];
for (const step of plan) {
  if (step.skip) {
    results.push({ name: step.name, status: "skip", note: step.skip });
    continue;
  }
  if (step.fail) {
    results.push({ name: step.name, status: "fail", note: step.fail });
    continue;
  }
  console.log(`\n=== ${step.name} ===`);
  const run = spawnSync(step.cmd, step.args, { cwd: root, stdio: "inherit", shell: shell && step.cmd !== plan.at(-1).cmd });
  results.push({ name: step.name, status: run.status === 0 ? "pass" : "fail", note: run.status === 0 ? undefined : `exit ${run.status}` });
}

console.log("\n=== check summary ===");
const { lines, ok } = summarize(results);
console.log(lines.join("\n"));
process.exit(ok ? 0 : 1);
