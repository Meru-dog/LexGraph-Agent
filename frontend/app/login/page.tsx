"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.replace("/");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
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
            LexGraph AI
          </div>
          <div className="text-[10px] uppercase tracking-[1.5px] text-[#9CA3AF] mt-0.5">
            AI Legal Research Platform
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1 block">
              Username
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full text-[13px] px-3 py-2 rounded-lg outline-none"
              style={{
                border: "1px solid #E5E7EB",
                color: "#111827",
                background: "#FAFAFA",
              }}
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
              style={{
                border: "1px solid #E5E7EB",
                color: "#111827",
                background: "#FAFAFA",
              }}
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
          className="mt-5 p-3 rounded-lg text-[11px] text-[#9CA3AF] leading-relaxed"
          style={{ background: "#F9FAFB", border: "1px solid #F3F4F6" }}
        >
          <strong className="text-[#6B7280]">Dev credentials:</strong>
          <br />
          attorney1 / secret · paralegal1 / secret · admin / secret
        </div>
      </div>
    </div>
  );
}
