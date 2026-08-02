import assert from "node:assert/strict";
import test from "node:test";

import { startTaskPolling } from "../../lib/taskPolling.js";

function jsonResponse(payload, { ok = true, status = 200, statusText = "OK" } = {}) {
  return {
    ok,
    status,
    statusText,
    async json() {
      return payload;
    },
  };
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

async function flushAsyncWork() {
  await new Promise((resolve) => setImmediate(resolve));
}

test("returns the raw result when a queued task completes", async (testContext) => {
  testContext.mock.timers.enable({ apis: ["setTimeout"] });
  const taskResponses = [
    jsonResponse({ status: "pending" }),
    jsonResponse({ status: "complete", result: { items: [{ id: 7 }] } }),
  ];
  testContext.mock.method(globalThis, "fetch", async () => taskResponses.shift());

  const completedTask = new Promise((resolve, reject) => {
    startTaskPolling("task-7", resolve, reject);
  });
  await flushAsyncWork();
  testContext.mock.timers.runAll();

  assert.deepEqual(await completedTask, { items: [{ id: 7 }] });
  assert.deepEqual(taskResponses, []);
});

test("reports a failed task once and stops polling", async (testContext) => {
  testContext.mock.method(
    globalThis,
    "fetch",
    async () => jsonResponse({ status: "failed", error: "provider_unavailable" }),
  );

  const taskError = await new Promise((resolve) => {
    startTaskPolling("task-failed", assert.fail, resolve);
  });

  assert.equal(taskError, "provider_unavailable");
});

test("reports an HTTP failure once and stops polling", async (testContext) => {
  testContext.mock.method(
    globalThis,
    "fetch",
    async () => jsonResponse(
      { detail: "backend unavailable" },
      { ok: false, status: 503, statusText: "Unavailable" },
    ),
  );

  const taskError = await new Promise((resolve) => {
    startTaskPolling("task-http-error", assert.fail, resolve);
  });

  assert.match(taskError.message, /Poll task failed \(HTTP 503\): backend unavailable/);
});

test("keeps a successful unreadable response pending until stopped", async (testContext) => {
  testContext.mock.timers.enable({ apis: ["setTimeout"] });
  let completed = false;
  let failed = false;
  const requestObserved = createDeferred();

  testContext.mock.method(globalThis, "fetch", async () => {
    requestObserved.resolve();
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      async json() {
        throw new SyntaxError("invalid JSON");
      },
    };
  });
  const stop = startTaskPolling(
    "task-empty-success",
    () => { completed = true; },
    () => { failed = true; },
  );
  await requestObserved.promise;
  await flushAsyncWork();

  assert.equal(completed, false);
  assert.equal(failed, false);
  stop();
});

test("uses status text when an unsuccessful response body is unreadable", async (testContext) => {
  testContext.mock.method(globalThis, "fetch", async () => ({
    ok: false,
    status: 502,
    statusText: "Bad Gateway",
    async json() {
      throw new SyntaxError("invalid JSON");
    },
  }));

  const taskError = await new Promise((resolve) => {
    startTaskPolling("task-unreadable-error", assert.fail, resolve);
  });

  assert.match(taskError.message, /Poll task failed \(HTTP 502\): Bad Gateway/);
});

test("reports a timeout after bounded polling attempts", async (testContext) => {
  testContext.mock.timers.enable({ apis: ["setTimeout"] });
  testContext.mock.method(
    globalThis,
    "fetch",
    async () => jsonResponse({ status: "pending" }),
  );

  let timeoutSettled = false;
  const timeoutError = new Promise((resolve) => {
    startTaskPolling("task-timeout", assert.fail, (error) => {
      timeoutSettled = true;
      resolve(error);
    });
  });
  await flushAsyncWork();
  for (let interval = 0; !timeoutSettled && interval < 50; interval += 1) {
    testContext.mock.timers.runAll();
    await flushAsyncWork();
  }

  assert.equal(timeoutSettled, true);
  assert.equal(await timeoutError, "task_poll_timeout");
});

test("stop suppresses completion after a pending request resolves", async (testContext) => {
  const pendingRequest = createDeferred();
  testContext.mock.method(globalThis, "fetch", () => pendingRequest.promise);
  let completed = false;
  let failed = false;

  const stop = startTaskPolling(
    "task-stopped-success",
    () => { completed = true; },
    () => { failed = true; },
  );
  stop();
  pendingRequest.resolve(jsonResponse({ status: "complete", result: { summary: "late" } }));
  await flushAsyncWork();

  assert.equal(completed, false);
  assert.equal(failed, false);
});

test("stop suppresses failure after a pending request rejects", async (testContext) => {
  const pendingRequest = createDeferred();
  testContext.mock.method(globalThis, "fetch", () => pendingRequest.promise);
  let completed = false;
  let failed = false;

  const stop = startTaskPolling(
    "task-stopped-failure",
    () => { completed = true; },
    () => { failed = true; },
  );
  stop();
  pendingRequest.reject(new Error("late network failure"));
  await flushAsyncWork();

  assert.equal(completed, false);
  assert.equal(failed, false);
});

test("stop aborts asynchronous completion before later state work", async (testContext) => {
  const completionStarted = createDeferred();
  const releaseCompletion = createDeferred();
  testContext.mock.method(
    globalThis,
    "fetch",
    async () => jsonResponse({ status: "complete", result: { extracted: true } }),
  );
  let updated = false;
  let failed = false;

  const stop = startTaskPolling(
    "task-async-completion",
    async (_taskResult, signal) => {
      completionStarted.resolve(signal);
      await releaseCompletion.promise;
      if (!signal.aborted) updated = true;
    },
    () => { failed = true; },
  );
  const completionSignal = await completionStarted.promise;
  stop();
  releaseCompletion.resolve();
  await flushAsyncWork();

  assert.equal(completionSignal.aborted, true);
  assert.equal(updated, false);
  assert.equal(failed, false);
});

test("stop clears a scheduled retry", async (testContext) => {
  testContext.mock.timers.enable({ apis: ["setTimeout"] });
  let firstRequest = true;
  let laterRequestObserved = false;
  const requestObserved = createDeferred();
  testContext.mock.method(
    globalThis,
    "fetch",
    async () => {
      if (firstRequest) {
        firstRequest = false;
        requestObserved.resolve();
      } else {
        laterRequestObserved = true;
      }
      return jsonResponse({ status: "pending" });
    },
  );

  const stop = startTaskPolling("task-stopped-retry", assert.fail, assert.fail);
  await requestObserved.promise;
  await flushAsyncWork();
  stop();
  testContext.mock.timers.runAll();
  await flushAsyncWork();

  assert.equal(laterRequestObserved, false);
});
