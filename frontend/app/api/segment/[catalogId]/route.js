import { proxyBackendJson } from "../../_lib/backend";

export async function POST(request, { params }) {
  return proxyBackendJson({
    method: "POST",
    path: `/segment/${params.catalogId}`,
    searchParams: request.nextUrl.searchParams,
  });
}
