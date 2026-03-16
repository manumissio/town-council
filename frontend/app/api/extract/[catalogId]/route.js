import { proxyBackendJson } from "../../_lib/backend";

export async function POST(request, { params }) {
  return proxyBackendJson({
    method: "POST",
    path: `/extract/${params.catalogId}`,
    searchParams: request.nextUrl.searchParams,
  });
}
