"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/", label: "Chat", icon: "💬" },
  { href: "/dd", label: "DD Agent", icon: "🔍" },
  { href: "/contract", label: "Contract Review", icon: "📄" },
  { href: "/tasks", label: "Tasks", icon: "📋" },
  { href: "/graph", label: "Knowledge Graph", icon: "🕸" },
  { href: "/upload", label: "Upload", icon: "⬆" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <aside
      className="w-[220px] flex-shrink-0 flex flex-col h-full bg-white border-r border-[#E5E7EB]"
      style={{ fontFamily: "var(--font-ibm-plex-sans)" }}
    >
      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b border-[#F3F4F6]">
        <div
          className="text-[21px] text-[#111827] leading-tight"
          style={{ fontFamily: "var(--font-dm-serif)" }}
        >
          LexGraph Agent
        </div>
        <div className="text-[9.5px] uppercase tracking-[1.5px] text-[#9CA3AF] mt-0.5 font-sans">
          Legal AI Platform
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] transition-colors rounded-none"
              style={{
                color: isActive ? "#2D4FD6" : "#6B7280",
                background: isActive ? "#EEF2FF" : "transparent",
                borderLeft: isActive ? "2px solid #2D4FD6" : "2px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = "#F1F3F8";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                }
              }}
            >
              <span className="text-sm">{icon}</span>
              <span className="font-medium">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User info + logout */}
      {user && (
        <div className="px-4 py-3 border-t border-[#F3F4F6] flex items-center justify-between">
          <div>
            <div className="text-[11px] font-semibold text-[#374151] truncate max-w-[130px]">
              {user.full_name || user.username}
            </div>
            <div className="text-[10px] text-[#9CA3AF] capitalize">{user.role}</div>
          </div>
          <button
            onClick={handleLogout}
            className="text-[10px] px-2 py-1 rounded text-[#6B7280] hover:text-[#DC2626] transition-colors"
            style={{ border: "1px solid #E5E7EB" }}
          >
            Out
          </button>
        </div>
      )}

      {/* Jurisdiction badge */}
      <div className="px-4 py-4 border-t border-[#F3F4F6]">
        <div
          className="rounded-md px-3 py-2 text-[11px]"
          style={{
            background: "#F0F4FF",
            border: "1px solid #C7D2FA",
          }}
        >
          <div className="text-[#4F46E5] font-semibold uppercase tracking-wide text-[10px]">
            Jurisdiction
          </div>
          <div className="text-[#6B7280] mt-0.5" style={{ fontFamily: "var(--font-ibm-plex-mono)" }}>
            🇯🇵 JP + 🇺🇸 US Active
          </div>
        </div>
        <div className="text-[10px] text-[#9CA3AF] mt-2 text-center">
          Graph RAG · Legal AI
        </div>
      </div>
    </aside>
  );
}
