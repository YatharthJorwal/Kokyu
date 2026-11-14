import { test } from "node:test";
import assert from "node:assert/strict";
import { checkPlan, summarize } from "../scripts/check-lib.mjs";

const base = { root: "/repo", platform: "linux", pythonExists: true, cargoAvailable: true };

test("the plan runs types, frontend tests, build, cargo and the kernel suite in that order", () => {
  const names = checkPlan(base).map((s) => s.name);
  assert.deepEqual(names, ["tsc", "frontend tests", "vite build", "cargo check", "pytest (kernel)"]);
});

test("pytest runs the KASANE folder with the venv python, or the override", () => {
  const venv = checkPlan(base).at(-1);
  assert.equal(venv.cmd, "/repo/.venv/bin/python");
  assert.deepEqual(venv.args.slice(0, 4), ["-m", "pytest", "KASANE", "-q"]);
  assert.equal(checkPlan({ ...base, python: "/x/py" }).at(-1).cmd, "/x/py");
  assert.match(checkPlan({ ...base, platform: "win32" }).at(-1).cmd, /\.venv.Scripts.python\.exe$/);
});

test("cargo is skipped with a stated reason, never silently", () => {
  assert.match(checkPlan({ ...base, skipCargo: true })[3].skip, /--skip-cargo/);
  assert.match(checkPlan({ ...base, cargoAvailable: false })[3].skip, /not found/);
  assert.ok(checkPlan(base)[3].cmd === "cargo");
});

test("a missing python is a failure with a fix, not a skip", () => {
  const step = checkPlan({ ...base, pythonExists: false }).at(-1);
  assert.match(step.fail, /KOKYU_PYTHON/);
});

test("a skipped step never reads as a full pass", () => {
  const ok = summarize([{ name: "a", status: "pass" }, { name: "cargo check", status: "skip", note: "cargo not found" }]);
  assert.equal(ok.ok, true);
  assert.match(ok.lines.at(-1), /not fully verified: skipped cargo check/);
  assert.match(summarize([{ name: "a", status: "pass" }]).lines.at(-1), /^GREEN: every step passed/);
  const red = summarize([{ name: "a", status: "fail", note: "exit 1" }, { name: "b", status: "pass" }]);
  assert.equal(red.ok, false);
  assert.match(red.lines.at(-1), /^RED/);
});
