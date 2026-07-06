import { apiFetch, type Site } from "@/lib/api";

/**
 * Where to land after authenticating (F2): brand-new accounts go straight to
 * the add-first-site flow; anyone with a site goes to the dashboard. Fails
 * open to the dashboard — routing must never block a successful sign-in.
 */
export async function postAuthPath(): Promise<string> {
  try {
    const sites = await apiFetch<Site[]>("/sites");
    return sites.length === 0 ? "/sites" : "/dashboard";
  } catch {
    return "/dashboard";
  }
}
