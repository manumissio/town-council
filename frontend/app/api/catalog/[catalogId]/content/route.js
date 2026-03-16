import { proxyBackendJson } from "../../../_lib/backend";

export async function GET(_request, { params }) {
  return proxyBackendJson({
    method: "GET",
    path: `/catalog/${params.catalogId}/content`,
  });
}
