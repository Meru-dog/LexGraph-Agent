"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import type { User, Session } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";

// Keep legacy shape for compatibility with existing code
interface AuthUser {
  username: string;
  full_name: string;
  role: string;
  email?: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  session: Session | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: "google" | "github") => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function supabaseUserToAuthUser(user: User): AuthUser {
  const meta = user.user_metadata ?? {};
  return {
    username: user.id,
    full_name: meta.full_name ?? meta.name ?? user.email?.split("@")[0] ?? "User",
    role: meta.role ?? "attorney",
    email: user.email,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const supabase = createClient(); // null when env vars not set

  useEffect(() => {
    if (!supabase) {
      // No Supabase — restore legacy session from localStorage
      const token = localStorage.getItem("lexgraph_access_token");
      if (token) {
        const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        fetch(`${BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
          .then((r) => r.ok ? r.json() : null)
          .then((me) => {
            if (me) setUser({ username: me.username, full_name: me.full_name, role: me.role });
          })
          .finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
      return;
    }

    // Restore session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ? supabaseUserToAuthUser(session.user) : null);
      setLoading(false);
    });

    // Listen for auth state changes (OAuth callback, logout, etc.)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ? supabaseUserToAuthUser(session.user) : null);
      setLoading(false);

      if (session?.access_token) {
        localStorage.setItem("lexgraph_access_token", session.access_token);
        if (session.refresh_token) {
          localStorage.setItem("lexgraph_refresh_token", session.refresh_token);
        }
      } else {
        localStorage.removeItem("lexgraph_access_token");
        localStorage.removeItem("lexgraph_refresh_token");
      }
    });

    return () => subscription.unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const login = async (username: string, password: string) => {
    // Try Supabase email/password if configured and input looks like email
    if (supabase && username.includes("@")) {
      const { error } = await supabase.auth.signInWithPassword({ email: username, password });
      if (error) throw new Error(error.message);
      return;
    }

    // Legacy: backend JWT endpoint for dev accounts
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const tokens = await res.json();
    localStorage.setItem("lexgraph_access_token", tokens.access_token);
    localStorage.setItem("lexgraph_refresh_token", tokens.refresh_token);

    const meRes = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    if (meRes.ok) {
      const me = await meRes.json();
      setUser({ username: me.username, full_name: me.full_name, role: me.role });
    }
  };

  const loginWithOAuth = async (provider: "google" | "github") => {
    if (!supabase) throw new Error("Supabase is not configured");
    await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  const logout = async () => {
    if (supabase) await supabase.auth.signOut();
    localStorage.removeItem("lexgraph_access_token");
    localStorage.removeItem("lexgraph_refresh_token");
    setUser(null);
    setSession(null);
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, login, loginWithOAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
