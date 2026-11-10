import { API_BASE } from "@/src/api";
import { storage } from "@/src/utils/storage";

// Admin portal session: an opaque server-side session token (never a password), kept in the
// secure keychain only when "Remember me" is chosen; otherwise it lives in memory for this visit.
const KEY = "travoo_admin_session";
let token: string | null = null;
let loaded = false;

export async function loadAdminToken(): Promise<string | null> {
  if (!loaded) {
    token = ((await storage.secureGet(KEY, "")) as string) || token;
    loaded = true;
  }
  return token;
}

export async function setAdminToken(t: string | null, remember = false) {
  token = t;
  loaded = true;
  if (t && remember) await storage.secureSet(KEY, t);
  else await storage.secureRemove(KEY);
}

export const getAdminToken = () => token;
export const adminFileUrl = (fid: string) => `${API_BASE}/files/${fid}?token=${encodeURIComponent(token ?? "")}`;

export class AdminAuthError extends Error {}

export async function adminApi<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = await loadAdminToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? (opts.body ? "POST" : "GET"),
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (data as any).detail;
    const msg = Array.isArray(d) ? `${d[0]?.loc?.slice(-1)[0] ?? ""}: ${d[0]?.msg}` : d;
    if (res.status === 401) {
      await setAdminToken(null);
      throw new AdminAuthError(msg || "Your admin session has ended. Please sign in again.");
    }
    throw new Error(msg || "Something went wrong");
  }
  return data as T;
}

export async function adminLogout() {
  try {
    await adminApi("/admin/auth/logout", { method: "POST" });
  } catch {
    // session may already be gone; local sign-out still happens
  }
  await setAdminToken(null);
}
