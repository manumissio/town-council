import { proxyBackendJson } from "../_lib/backend";

export async function POST(request) {
  return proxyBackendJson({
    method: "POST",
    path: "/report-issue",
    body: await request.text(),
  });
}
