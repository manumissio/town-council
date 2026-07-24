import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import { proxyBackendJson } from "../../app/api/_lib/backend.js";

const API_AUTH_KEY = "frontend-proxy-test-key";
const BLOCKED_DETAIL = "Cross-site mutation requests are not allowed.";
const FRONTEND_ORIGIN = "https://town-council.example";
const INTERNAL_ORIGIN = "http://0.0.0.0:3000";
const ROUTE_ROOT = path.resolve(process.cwd(), "app/api");
const originalApiAuthKey = process.env.API_AUTH_KEY;
const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalApiAuthKey === undefined) {
    delete process.env.API_AUTH_KEY;
  } else {
    process.env.API_AUTH_KEY = originalApiAuthKey;
  }
});

function makePostRequest(headers = {}, requestOrigin = FRONTEND_ORIGIN) {
  return new Request(`${requestOrigin}/api/summarize/42`, {
    method: "POST",
    headers,
  });
}

function makeStandalonePost(headers) {
  return makePostRequest(headers, INTERNAL_ORIGIN);
}

function rejectUnexpectedBackendAccess() {
  globalThis.fetch = async () => {
    throw new Error("Blocked mutation reached the backend.");
  };
}

function installBackendResponse() {
  process.env.API_AUTH_KEY = API_AUTH_KEY;
  globalThis.fetch = async (_backendUrl, backendOptions) => {
    assert.equal(backendOptions.headers.get("X-API-Key"), API_AUTH_KEY);
    return Response.json({ status: "queued" }, { status: 202 });
  };
}

async function assertBlocked(request, method = "POST") {
  rejectUnexpectedBackendAccess();
  delete process.env.API_AUTH_KEY;

  const proxyResponse = await proxyBackendJson({
    request,
    method,
    path: "/summarize/42",
  });

  assert.equal(proxyResponse.status, 403);
  assert.match(proxyResponse.headers.get("content-type"), /application\/json/);
  assert.deepEqual(await proxyResponse.json(), { detail: BLOCKED_DETAIL });
}

function findRouteFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return findRouteFiles(entryPath);
    }
    return entry.name === "route.js" ? [entryPath] : [];
  });
}

test("rejects cross-site and same-site Fetch Metadata", async () => {
  for (const fetchSite of ["cross-site", "same-site"]) {
    await assertBlocked(makePostRequest({ "Sec-Fetch-Site": fetchSite }));
  }
});
test("rejects Origin mismatches by scheme, host, and port", async () => {
  const mismatchedOrigins = [
    "http://town-council.example",
    "https://admin.town-council.example",
    "https://town-council.example:8443",
  ];

  for (const origin of mismatchedOrigins) {
    await assertBlocked(makePostRequest({ Origin: origin }));
  }
});
test("rejects null and malformed Origin values", async () => {
  for (const origin of [
    "null",
    "not-an-origin",
    "https://town-council.example/not-an-origin-component",
  ]) {
    await assertBlocked(makePostRequest({ Origin: origin }));
  }
});
test("blocked Fetch Metadata overrides a matching Origin", async () => {
  await assertBlocked(
    makePostRequest({
      Origin: FRONTEND_ORIGIN,
      "Sec-Fetch-Site": "cross-site",
    }),
  );
});
test("unknown Fetch Metadata falls back to Origin validation", async () => {
  await assertBlocked(
    makePostRequest({
      Origin: "https://other.example",
      "Sec-Fetch-Site": "future-value",
    }),
  );
});
test("same-origin POST forwards the backend response", async () => {
  installBackendResponse();

  const proxyResponse = await proxyBackendJson({
    request: makePostRequest({
      Origin: FRONTEND_ORIGIN,
      "Sec-Fetch-Site": "same-origin",
    }),
    method: "POST",
    path: "/summarize/42",
  });

  assert.equal(proxyResponse.status, 202);
  assert.deepEqual(await proxyResponse.json(), { status: "queued" });
});
test("headerless POST preserves non-browser callers", async () => {
  installBackendResponse();

  const proxyResponse = await proxyBackendJson({
    request: makePostRequest(),
    method: "POST",
    path: "/summarize/42",
  });

  assert.equal(proxyResponse.status, 202);
  assert.deepEqual(await proxyResponse.json(), { status: "queued" });
});

test("standalone internal URL honors external Host and protocol", async () => {
  const externalRequests = [
    makeStandalonePost({
      Host: "localhost:3124",
      Origin: "http://localhost:3124",
      "Sec-Fetch-Site": "same-origin",
    }),
    makeStandalonePost({
      Host: "town-council.example",
      Origin: FRONTEND_ORIGIN,
      "Sec-Fetch-Site": "same-origin",
      "X-Forwarded-Proto": "https, http",
    }),
    makeStandalonePost({
      Host: "town-council.example:80",
      Origin: "https://town-council.example:80",
      "X-Forwarded-Proto": "https",
    }),
  ];

  for (const request of externalRequests) {
    installBackendResponse();
    const proxyResponse = await proxyBackendJson({
      request,
      method: "POST",
      path: "/summarize/42",
    });
    assert.equal(proxyResponse.status, 202);
  }
});

test("rejects malformed proxy metadata and forwarded-port mismatches", async () => {
  const malformedHeaders = [
    { Host: "[invalid", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example@attacker.example", Origin: "https://attacker.example", "X-Forwarded-Proto": "https" },
    { Host: "town-council.example/path", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example/", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example?", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example#", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example\\", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
    { Host: "town-council.example", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "javascript" },
    { Host: "town-council.example", Origin: "https://attacker.example", "X-Forwarded-Proto": "https://attacker.example/path?" },
    { Host: "town-council.example", Origin: "http://town-council.example", "X-Forwarded-Proto": "   " },
    { Host: "town-council.example", Origin: "http://town-council.example", "X-Forwarded-Proto": ", https" },
    { Host: "town-council.example:80", Origin: FRONTEND_ORIGIN, "X-Forwarded-Proto": "https" },
  ];

  for (const headers of malformedHeaders) {
    await assertBlocked(makeStandalonePost(headers));
  }
});

test("does not trust X-Forwarded-Host over the standard Host", async () => {
  await assertBlocked(
    makePostRequest(
      {
        Host: "town-council.example",
        Origin: "https://attacker.example",
        "Sec-Fetch-Site": "future-value",
        "X-Forwarded-Host": "attacker.example",
        "X-Forwarded-Proto": "https",
      },
      "http://0.0.0.0:3000",
    ),
  );
});

test("POST without its request fails before backend access", async () => {
  rejectUnexpectedBackendAccess();
  process.env.API_AUTH_KEY = API_AUTH_KEY;

  await assert.rejects(
    proxyBackendJson({
      method: "POST",
      path: "/summarize/42",
    }),
    TypeError,
  );
});
test("cross-site POST cannot bypass the guard through proxy method metadata", async () => {
  await assertBlocked(
    makePostRequest({ "Sec-Fetch-Site": "cross-site" }),
    "GET",
  );
});

test("allowed POST without API_AUTH_KEY keeps the configuration error", async () => {
  rejectUnexpectedBackendAccess();
  delete process.env.API_AUTH_KEY;

  const proxyResponse = await proxyBackendJson({
    request: makePostRequest({ Origin: FRONTEND_ORIGIN }),
    method: "POST",
    path: "/summarize/42",
  });

  assert.equal(proxyResponse.status, 500);
  assert.deepEqual(await proxyResponse.json(), {
    detail: "Frontend backend proxy is not configured.",
  });
});

test("every POST route passes its request to the shared proxy", () => {
  const postRouteSources = findRouteFiles(ROUTE_ROOT)
    .map((routePath) => ({
      routePath,
      source: fs.readFileSync(routePath, "utf8"),
    }))
    .filter(({ source }) => /export async function POST/.test(source));

  assert.ok(postRouteSources.length > 0);
  for (const { routePath, source } of postRouteSources) {
    const proxyOptions = source.match(
      /proxyBackendJson\(\{(?<options>[\s\S]*?)\}\)/,
    )?.groups?.options;
    assert.ok(proxyOptions, `${routePath} must call proxyBackendJson`);
    assert.match(
      proxyOptions,
      /\brequest\s*,/,
      `${routePath} must pass request to proxyBackendJson`,
    );
    assert.match(proxyOptions, /method:\s*"POST"/, `${routePath} must use POST`);
  }
});
