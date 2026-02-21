import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const cardPath = path.resolve(process.cwd(), "components/ResultCard.js");
const cardSource = fs.readFileSync(cardPath, "utf8");

test("uses bounded polling with timeout signaling", () => {
  assert.match(cardSource, /TASK_POLL_MAX_ATTEMPTS/);
  assert.match(cardSource, /task_poll_timeout/);
  assert.match(cardSource, /setTimeout\(/);
});

test("tracks poll stop handlers for cleanup on unmount", () => {
  assert.match(cardSource, /activePollStopsRef/);
  assert.match(cardSource, /addPollStop/);
  assert.match(cardSource, /return \(\) => \{/);
});
