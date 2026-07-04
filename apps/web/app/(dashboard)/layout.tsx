"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { UsageBanner } from "@/components/UsageBanner";
import { useMe } from "@/hooks/useAuth";

// Client-side guard (plan D1): validate the session via /auth/me. The access
// token lives in memory, so on a fresh load this triggers a refresh from the
// stored refresh token; if that fails the query errors and we redirect.
export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data, isLoading, isError } = useMe();

  useEffect(() => {
    if (!isLoading && isError) {
      router.replace("/sign-in");
    }
  }, [isLoading, isError, router]);

  if (isLoading) {
    return <main className="flex flex-1 items-center justify-center">Loading…</main>;
  }
  if (isError || !data) {
    return null; // redirecting
  }
  return (
    <>
      <UsageBanner />
      {children}
    </>
  );
}
