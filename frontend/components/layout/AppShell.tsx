"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ChatProvider } from "@/context/ChatContext";
import { DDProvider } from "@/context/DDContext";
import { ContractReviewProvider } from "@/context/ContractReviewContext";
import Sidebar from "./Sidebar";

function GuardedLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [user, loading, pathname, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#F5F6F8]">
        <div className="text-[13px] text-[#9CA3AF]">Loading…</div>
      </div>
    );
  }

  // Render login page without sidebar
  if (!user) {
    return <main className="flex-1 overflow-hidden">{children}</main>;
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-hidden">{children}</main>
    </>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ChatProvider>
        <DDProvider>
          <ContractReviewProvider>
            <GuardedLayout>{children}</GuardedLayout>
          </ContractReviewProvider>
        </DDProvider>
      </ChatProvider>
    </AuthProvider>
  );
}
