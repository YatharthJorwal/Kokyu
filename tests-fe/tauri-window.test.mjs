import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const conf = JSON.parse(
  readFileSync(join(process.cwd(), "src-tauri", "tauri.conf.json"), "utf8"),
);

test("the main window is a normal app window, not the old widget (K1-00d)", () => {
  const w = conf.app.windows.find((x) => x.label === "main");
  assert.ok(w);
  assert.equal(w.decorations, true);
  assert.equal(w.transparent, false);
  assert.equal(w.alwaysOnTop, false);
  assert.ok(w.width >= 1000 && w.height >= 700);
  assert.ok(w.minWidth >= 800 && w.minHeight >= 560);
});

for (const key of ["csp", "devCsp"]) {
  test(`${key}: scripts only from the app, the kernel reachable, nothing else`, () => {
    const csp = conf.app.security[key];
    assert.ok(csp && typeof csp === "object", `${key} must be set`);
    // Production: app scripts only. Dev: Vite's React plugin injects one inline
    // module (the fast-refresh preamble, K1-02), so dev alone allows inline scripts.
    assert.equal(csp["script-src"], key === "csp" ? "'self'" : "'self' 'unsafe-inline'");
    assert.equal(csp["object-src"], "'none'");
    for (const directive of Object.values(csp)) {
      assert.doesNotMatch(directive, /unsafe-eval|\*/);
    }
    assert.match(csp["connect-src"], /ws:\/\/127\.0\.0\.1:8780/);
    assert.match(csp["connect-src"], /http:\/\/127\.0\.0\.1:8780/);
    assert.match(csp["img-src"], /blob:/); // VRM textures are decoded through blob URLs
    assert.match(csp["media-src"], /data:|blob:/); // voice clips
  });
}
