import { NextResponse } from "next/server";

function getInternalApiBaseUrl() {
  return process.env.INTERNAL_API_BASE_URL || "http://api:8000";
}

function getApiAuthKey() {
  const apiAuthKey = process.env.API_AUTH_KEY;
  if (!apiAuthKey) {
    throw new Error("API_AUTH_KEY is required for frontend backend proxy routes.");
  }
  return apiAuthKey;
}

export function buildBackendUrl(path, searchParams) {
  const url = new URL(path, getInternalApiBaseUrl());
  if (searchParams) {
    url.search = searchParams.toString();
  }
  return url;
}

export async function proxyBackendJson({
  method,
  path,
  searchParams,
  body,
}) {
  let apiAuthKey;
  try {
    apiAuthKey = getApiAuthKey();
  } catch (error) {
    console.error("frontend_backend_proxy.missing_auth_env", error);
    return NextResponse.json(
      { detail: "Frontend backend proxy is not configured." },
      { status: 500 },
    );
  }

  const headers = new Headers({
    "X-API-Key": apiAuthKey,
  });

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildBackendUrl(path, searchParams), {
    method,
    headers,
    body,
    cache: "no-store",
  });
  const text = await response.text();

  return new Response(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") || "application/json",
    },
  });
}
