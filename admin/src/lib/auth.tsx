import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, clearToken, login as loginRequest, me, readToken, writeToken } from "./api";
import type { AdminProfile } from "./types";

/**
 * Console session.
 *
 * The token lives in `localStorage`: this is an internal tool on its own origin,
 * and there is no server-rendered shell that needs to know about the session.
 * On boot the stored token is verified with `GET /auth/me`, so a stale one is
 * discarded before any page tries to use it.
 */

interface AuthState {
  token: string | null;
  profile: AdminProfile | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [profile, setProfile] = useState<AdminProfile | null>(null);
  const [ready, setReady] = useState(false);

  const verify = useCallback(async (candidate: string | null) => {
    if (!candidate) {
      setReady(true);
      return;
    }
    try {
      const who = await me();
      setToken(candidate);
      setProfile(who);
    } catch (error) {
      // 401 means the token is stale; anything else is a network problem, and
      // either way the console cannot do anything useful without a session.
      if (error instanceof ApiError && error.status !== 401) {
        console.error("session check failed", error);
      }
      clearToken();
      setToken(null);
      setProfile(null);
    } finally {
      setReady(true);
    }
  }, []);

  // Verify the stored token once, before any page decides what to render.
  useEffect(() => {
    void verify(readToken());
  }, [verify]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const result = await loginRequest(email, password);
      writeToken(result.access_token);
      setToken(result.access_token);
      setProfile(await me());
    },
    [],
  );

  const signOut = useCallback(() => {
    clearToken();
    setToken(null);
    setProfile(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ token, profile, ready, signIn, signOut }),
    [token, profile, ready, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
