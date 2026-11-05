import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

import { api, setApiToken, setUnauthorizedHandler } from "@/src/api";
import { storage } from "@/src/utils/storage";

WebBrowser.maybeCompleteAuthSession();

const TOKEN_KEY = "travoo_token";

export type User = {
  user_id: string;
  email: string;
  name: string;
  phone?: string;
  role: "user" | "admin";
  language: string;
  picture?: string | null;
  upi_id?: string;
  bio?: string;
  driver_status: "not_submitted" | "under_review" | "approved" | "rejected" | "resubmit";
  rating_avg: number;
  rating_count: number;
};

type Ctx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (b: { email: string; password: string; name: string; phone: string; language: string; consent: boolean }) => Promise<void>;
  googleLogin: () => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (u: User) => void;
};

const AuthContext = createContext<Ctx | null>(null);
const extractSessionId = (url?: string | null) => url?.match(/[?#&]session_id=([^&#]+)/)?.[1] ?? null;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const used = useRef(new Set<string>());

  const clear = useCallback(async () => {
    setApiToken(null);
    await storage.secureRemove(TOKEN_KEY);
    setUser(null);
  }, []);

  const saveSession = useCallback(async (token: string, u: User) => {
    setApiToken(token);
    await storage.secureSet(TOKEN_KEY, token);
    setUser(u);
  }, []);

  const exchange = useCallback(
    async (sessionId: string) => {
      if (used.current.has(sessionId)) return false;
      used.current.add(sessionId);
      try {
        const r = await api<{ session_token: string; user: User }>("/auth/session", { body: { session_id: sessionId } });
        await saveSession(r.session_token, r.user);
        return true;
      } catch {
        return false;
      }
    },
    [saveSession],
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clear();
    });
    (async () => {
      if (Platform.OS === "web" && typeof window !== "undefined") {
        const sid = extractSessionId(window.location.href);
        if (sid) {
          if (await exchange(sid)) {
            window.history.replaceState(window.history.state, "", window.location.pathname);
            setLoading(false);
            return;
          }
        }
      } else {
        const sid = extractSessionId(await Linking.getInitialURL());
        if (sid && (await exchange(sid))) {
          setLoading(false);
          return;
        }
      }
      const tok = (await storage.secureGet(TOKEN_KEY, "")) as string;
      if (tok) {
        setApiToken(tok);
        try {
          setUser(await api<User>("/auth/me"));
        } catch {
          await clear();
        }
      }
      setLoading(false);
    })();
    if (Platform.OS !== "web") {
      const sub = Linking.addEventListener("url", ({ url }) => {
        const sid = extractSessionId(url);
        if (sid) exchange(sid);
      });
      return () => sub.remove();
    }
  }, [clear, exchange]);

  const login = useCallback(
    async (email: string, password: string) => {
      const r = await api<{ token: string; user: User }>("/auth/login", { body: { email, password } });
      await saveSession(r.token, r.user);
    },
    [saveSession],
  );

  const register = useCallback(
    async (b: { email: string; password: string; name: string; phone: string; language: string; consent: boolean }) => {
      const r = await api<{ token: string; user: User }>("/auth/register", { body: b });
      await saveSession(r.token, r.user);
    },
    [saveSession],
  );

  const googleLogin = useCallback(async () => {
    const redirect = Platform.OS === "web" ? `${window.location.origin}/` : Linking.createURL("");
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirect)}`;
    if (Platform.OS === "web") {
      window.location.href = authUrl;
      return;
    }
    let captured: string | null = null;
    const sub = Linking.addEventListener("url", ({ url }) => {
      captured = url;
    });
    try {
      const res = await WebBrowser.openAuthSessionAsync(authUrl, redirect);
      const url = (res.type === "success" ? res.url : null) ?? captured ?? (await Linking.getInitialURL());
      const sid = extractSessionId(url);
      if (sid) await exchange(sid);
    } finally {
      sub.remove();
    }
  }, [exchange]);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {}
    await clear();
  }, [clear]);

  const refresh = useCallback(async () => {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {}
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, googleLogin, logout, refresh, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}
