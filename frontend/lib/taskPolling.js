import { buildApiUrl, readJsonResponse } from "./api.js";

const TASK_POLL_INITIAL_INTERVAL_MS = 1500;
const TASK_POLL_MAX_INTERVAL_MS = 5000;
const TASK_POLL_MAX_ATTEMPTS = 45;

export function startTaskPolling(taskId, onComplete, onError) {
  let active = true;
  let timeoutId = null;
  const abortController = new AbortController();

  const stop = () => {
    active = false;
    if (!abortController.signal.aborted) abortController.abort();
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  const fetchTaskStatus = async () => {
    try {
      const response = await fetch(buildApiUrl(`/tasks/${taskId}`), {
        signal: abortController.signal,
      });
      return await readJsonResponse(response, "Poll task");
    } catch (error) {
      if (!active) return null;
      console.error("Polling error", error);
      stop();
      onError(error);
      return null;
    }
  };

  const checkStatus = async () => {
    if (!active) return true;
    const taskStatus = await fetchTaskStatus();

    // Unmount cleanup may run while HTTP or JSON work is still pending.
    if (!active || taskStatus === null) return true;
    if (taskStatus.status === "complete") {
      try {
        await onComplete(taskStatus.result, abortController.signal);
      } catch (error) {
        if (!active) return true;
        console.error("Task completion callback failed", error);
        stop();
        onError(error);
        return true;
      }
      stop();
      return true;
    }
    if (taskStatus.status === "failed") {
      console.error("Task failed", taskStatus.error);
      stop();
      onError(taskStatus.error);
      return true;
    }
    return false;
  };

  const tick = async (attempt = 1, intervalMs = TASK_POLL_INITIAL_INTERVAL_MS) => {
    const isDone = await checkStatus();
    if (isDone || !active) {
      stop();
      return;
    }
    if (attempt >= TASK_POLL_MAX_ATTEMPTS) {
      stop();
      onError("task_poll_timeout");
      return;
    }

    const nextIntervalMs = Math.min(
      Math.round(intervalMs * 1.35),
      TASK_POLL_MAX_INTERVAL_MS,
    );
    timeoutId = setTimeout(() => {
      void tick(attempt + 1, nextIntervalMs);
    }, intervalMs);
  };

  void tick();
  return stop;
}
