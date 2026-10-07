"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, getToken, setToken } from "./api";
import type { Health, Role, TokenOut, User } from "./types";

const USER_KEY = "kp.user";

interface AuthState {
  user: User | null;
  ready: boolean;
  health: Health | null;
  login: (email: string, password: string) => Promise<User>;
  register: (body: Record<string, unknown>) => Promise<User>;
  logout: () => void;
  refreshHealth: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function homeFor(role: Role) {
  return role === "candidate" ? "/candidate" : role === "assessor" ? "/assessor" : "/admin";
}

function cacheUser(u: User | null) {
  try {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.get<Health>("/health"));
    } catch {
      /* offline: keep last known */
    }
  }, []);

  useEffect(() => {
    // Restore the session. The cached user keeps the candidate app usable offline.
    let cached: User | null = null;
    try {
      const raw = localStorage.getItem(USER_KEY);
      cached = raw ? (JSON.parse(raw) as User) : null;
    } catch {
      cached = null;
    }
    if (!getToken()) {
      // Session restore must run after hydration (localStorage is client-only), so this effect is intended.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setReady(true);
    } else {
      setUser(cached);
      api
        .get<User>("/auth/me")
        .then((u) => {
          setUser(u);
          cacheUser(u);
        })
        .catch((e) => {
          if (e instanceof ApiError && e.status === 401) {
            setUser(null);
            cacheUser(null);
          }
        })
        .finally(() => setReady(true));
    }
    refreshHealth();
  }, [refreshHealth]);

  const login = useCallback(async (email: string, password: string) => {
    const out = await api.post<TokenOut>("/auth/login", { email, password });
    setToken(out.access_token);
    cacheUser(out.user);
    setUser(out.user);
    return out.user;
  }, []);

  const register = useCallback(async (body: Record<string, unknown>) => {
    const out = await api.post<TokenOut>("/auth/register", body);
    setToken(out.access_token);
    cacheUser(out.user);
    setUser(out.user);
    return out.user;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    cacheUser(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, ready, health, login, register, logout, refreshHealth }),
    [user, ready, health, login, register, logout, refreshHealth],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export function useIsDemo() {
  return useAuth().health?.mode === "demo";
}

/** Redirects away unless the signed-in user has one of `roles`. Returns the user when allowed. */
export function useRequireRole(roles: Role[]): User | null {
  const { user, ready } = useAuth();
  const router = useRouter();
  const allowed = !!user && roles.includes(user.role);
  useEffect(() => {
    if (!ready) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
    else if (!roles.includes(user.role)) router.replace(homeFor(user.role));
    // roles is a literal at each call site
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, user, router]);
  return allowed ? user : null;
}
