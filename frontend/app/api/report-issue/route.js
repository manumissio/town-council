import { proxyBackendJson } from "../_lib/backend";

export async function POST(request) {
  return proxyBackendJson({
    request,
    method: "POST",
    path: "/report-issue",
    body: await request.text(),
  });
}
