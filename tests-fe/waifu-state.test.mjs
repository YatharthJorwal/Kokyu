import { test } from "node:test";
import assert from "node:assert/strict";
import {
  captionOnlyDurationMs,
  kernelHttpBase,
  needsAvatarReload,
  resolveModelPath,
  vrmUrl,
  waifuOptions,
} from "../src/waifu-state.ts";

test("the kernel's http base is derived from its websocket url", () => {
  assert.equal(kernelHttpBase("ws://127.0.0.1:8780/ws"), "http://127.0.0.1:8780");
  assert.equal(kernelHttpBase("wss://example.test:9/ws?surface=shell"), "https://example.test:9");
});

test("a waifu's avatar comes from the kernel, escaped", () => {
  assert.equal(vrmUrl("http://127.0.0.1:8780", "luna"), "http://127.0.0.1:8780/waifus/luna/vrm");
  assert.equal(vrmUrl("http://h", "a/b"), "http://h/waifus/a%2Fb/vrm");
});

test("startup avatar: the stored waifu's, else the legacy default", () => {
  assert.equal(resolveModelPath("yuri", "/vrm/yuri.vrm", "http://h"), "http://h/waifus/yuri/vrm");
  assert.equal(resolveModelPath(null, "/vrm/yuri.vrm", "http://h"), "/vrm/yuri.vrm");
});

test("reload only when the kernel names a different waifu than the one on screen", () => {
  assert.equal(needsAvatarReload("luna", "luna"), false);
  assert.equal(needsAvatarReload("luna", "yuri"), true);
  assert.equal(needsAvatarReload(null, "luna"), true);   // first launch: load the real avatar once
  assert.equal(needsAvatarReload("luna", null), false);  // no packs installed: never reload
  assert.equal(needsAvatarReload(null, null), false);
});

test("caption-only duration scales with the text and is bounded", () => {
  assert.equal(captionOnlyDurationMs(""), 1200);
  assert.equal(captionOnlyDurationMs("x".repeat(40)), 1200 + 55 * 40);
  assert.equal(captionOnlyDurationMs("x".repeat(500)), 6000);
});

test("the list marks the pending waifu while a switch waits for the current turn", () => {
  const msg = {
    type: "waifu_state",
    active: "luna",
    pending: "yuri",
    problems: [],
    waifus: [
      { id: "luna", name: "Luna", premade: true, traits: ["a"] },
      { id: "yuri", name: "Yuri", premade: true, traits: ["b"] },
    ],
  };
  assert.deepEqual(
    waifuOptions(msg).map((o) => [o.value, o.selected]),
    [["luna", false], ["yuri", true]],
  );
  assert.deepEqual(waifuOptions({ ...msg, pending: undefined }).map((o) => o.selected), [true, false]);
});
