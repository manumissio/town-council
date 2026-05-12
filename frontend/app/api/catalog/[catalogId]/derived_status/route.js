import { proxyBackendJson } from "../../../_lib/backend";

export async function GET(_request, { params }) {
  const { catalogId } = await params;
  return proxyBackendJson({
    method: "GET",
    path: `/catalog/${catalogId}/derived_status`,
  });
}
