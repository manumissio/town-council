import { proxyBackendJson } from "../../_lib/backend";

export async function POST(request, { params }) {
  const { catalogId } = await params;
  return proxyBackendJson({
    request,
    method: "POST",
    path: `/summarize/${catalogId}`,
    searchParams: request.nextUrl.searchParams,
  });
}
