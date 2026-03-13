"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { isSupabaseConfigured } from "@/lib/supabase/client";

export default function LoginPage() {
  const { login, loginWithOAuth } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: "google" | "github") => {
    setError("");
    setOauthLoading(provider);
    try {
      await loginWithOAuth(provider);
      // Redirect handled by OAuth callback
    } catch (err) {
      setError(`OAuth sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
      setOauthLoading(null);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-[#F5F6F8]"
      style={{ fontFamily: "var(--font-ibm-plex-sans)" }}
    >
      <div
        className="w-[360px] bg-white rounded-xl p-8 shadow-sm"
        style={{ border: "1px solid #E5E7EB" }}
      >
        {/* Logo */}
        <div className="mb-7 text-center">
          <div
            className="text-[26px] text-[#111827] leading-tight"
            style={{ fontFamily: "var(--font-dm-serif)" }}
          >
            LexGraph Agent
          </div>
          <div className="text-[10px] uppercase tracking-[1.5px] text-[#9CA3AF] mt-0.5">
            Legal AI Platform
          </div>
        </div>

        {/* OAuth buttons — only shown when Supabase is configured */}
        {isSupabaseConfigured && (<div className="flex flex-col gap-2 mb-5">
          <button
            onClick={() => handleOAuth("google")}
            disabled={!!oauthLoading || loading}
            className="w-full flex items-center justify-center gap-2.5 py-2.5 rounded-lg text-[13px] font-medium transition-colors"
            style={{
              border: "1px solid #E5E7EB",
              color: "#374151",
              background: oauthLoading === "google" ? "#F9FAFB" : "#FFFFFF",
              opacity: oauthLoading && oauthLoading !== "google" ? 0.5 : 1,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            {oauthLoading === "google" ? "Redirecting…" : "Continue with Google"}
          </button>
          <button
            onClick={() => handleOAuth("github")}
            disabled={!!oauthLoading || loading}
            className="w-full flex items-center justify-center gap-2.5 py-2.5 rounded-lg text-[13px] font-medium transition-colors"
            style={{
              border: "1px solid #E5E7EB",
              color: "#374151",
              background: oauthLoading === "github" ? "#F9FAFB" : "#FFFFFF",
              opacity: oauthLoading && oauthLoading !== "github" ? 0.5 : 1,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
            </svg>
            {oauthLoading === "github" ? "Redirecting…" : "Continue with GitHub"}
          </button>
        </div>)}

        {isSupabaseConfigured && (
          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#E5E7EB]" />
            </div>
            <div className="relative flex justify-center text-[11px]">
              <span className="bg-white px-2 text-[#9CA3AF]">or use dev account</span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1 block">
              Username / Email
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full text-[13px] px-3 py-2 rounded-lg outline-none"
              style={{ border: "1px solid #E5E7EB", color: "#111827", background: "#FAFAFA" }}
              placeholder="attorney1"
            />
          </div>

          <div>
            <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1 block">
              Password
            </label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full text-[13px] px-3 py-2 rounded-lg outline-none"
              style={{ border: "1px solid #E5E7EB", color: "#111827", background: "#FAFAFA" }}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="text-[12px] text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 text-[13px] font-semibold text-white rounded-lg transition-opacity"
            style={{ background: loading ? "#9CA3AF" : "#2D4FD6" }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div
          className="mt-4 p-3 rounded-lg text-[11px] text-[#9CA3AF] leading-relaxed"
          style={{ background: "#F9FAFB", border: "1px solid #F3F4F6" }}
        >
          <strong className="text-[#6B7280]">Dev accounts:</strong>{" "}
          attorney1 / secret · paralegal1 / secret · admin / secret
        </div>
      </div>
    </div>
  );
}
