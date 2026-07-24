import { proxyBackendJson } from "../../_lib/backend";

export async function POST(request, { params }) {
  const { catalogId } = await params;
  return proxyBackendJson({
    request,
    method: "POST",
    path: `/topics/${catalogId}`,
    searchParams: request.nextUrl.searchParams,
  });
}
