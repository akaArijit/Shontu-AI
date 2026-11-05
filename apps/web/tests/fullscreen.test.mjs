import assert from "node:assert/strict";
import test from "node:test";

import {
  fullscreenWorkspaceClass,
  graphCanvasClass,
  nextFullscreenState,
} from "../src/lib/fullscreen.ts";

test("fullscreen state enters and exits through the button and Escape", () => {
  assert.equal(nextFullscreenState(false, "enter"), true);
  assert.equal(nextFullscreenState(true, "exit"), false);
  assert.equal(nextFullscreenState(false, "toggle"), true);
  assert.equal(nextFullscreenState(true, "toggle"), false);
  assert.equal(nextFullscreenState(true, "escape"), false);
  assert.equal(nextFullscreenState(false, "escape"), false);
});

test("fullscreen workspace covers the viewport and returns to normal", () => {
  assert.match(fullscreenWorkspaceClass(true), /fixed inset-0/);
  assert.match(fullscreenWorkspaceClass(true), /overflow-y-auto/);
  assert.equal(fullscreenWorkspaceClass(false), "");
});

test("fullscreen graph is responsive instead of using the page canvas height", () => {
  const normal = graphCanvasClass(false);
  const fullscreen = graphCanvasClass(true);

  assert.match(normal, /h-\[78vh\]/);
  assert.match(normal, /min-h-\[760px\]/);
  assert.match(fullscreen, /h-\[calc\(100vh-270px\)\]/);
  assert.match(fullscreen, /min-h-\[420px\]/);
  assert.match(fullscreen, /w-full/);
  assert.match(fullscreen, /bg-peach-200/);
  assert.match(fullscreen, /border-warm-500\/30/);
  assert.notEqual(normal, fullscreen);
});
