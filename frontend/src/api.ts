const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export const setApiToken = (t: string | null) => {
  token = t;
};
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? (opts.body ? "POST" : "GET"),
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized?.();
    const d = (data as any).detail;
    const msg = Array.isArray(d) ? `${d[0]?.loc?.slice(-1)[0] ?? ""}: ${d[0]?.msg}` : d;
    throw new Error(msg || "Something went wrong");
  }
  return data as T;
}

export type Loc = {
  loc_id: string;
  name: string;
  type: string;
  district?: string;
  state?: string;
  pin?: string | null;
  lat: number;
  lng: number;
  aliases?: string[];
  source?: string;
};

export const locPayload = (l: Loc) => ({
  loc_id: l.loc_id,
  name: l.name,
  type: l.type,
  district: l.district ?? "",
  state: l.state ?? "",
  pin: l.pin ?? null,
  lat: l.lat,
  lng: l.lng,
});
