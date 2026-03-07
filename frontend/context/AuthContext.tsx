"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { login as apiLogin, getMe, refreshToken as apiRefresh } from "@/lib/api";
import { setTokens, clearTokens, getRefreshToken } from "@/lib/auth";

interface AuthUser {
  username: string;
  full_name: string;
  role: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: try to restore session from stored tokens
  useEffect(() => {
    const restore = async () => {
      try {
        const me = await getMe();
        setUser(me);
      } catch {
        // Try refresh
        const refresh = getRefreshToken();
        if (refresh) {
          try {
            const tokens = await apiRefresh(refresh);
            setTokens(tokens.access_token, tokens.refresh_token);
            const me = await getMe();
            setUser(me);
          } catch {
            clearTokens();
          }
        }
      } finally {
        setLoading(false);
      }
    };
    restore();
  }, []);

  const login = async (username: string, password: string) => {
    const tokens = await apiLogin(username, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    const me = await getMe();
    setUser(me);
  };

  const logout = () => {
    clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
