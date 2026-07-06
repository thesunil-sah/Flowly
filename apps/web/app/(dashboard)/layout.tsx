"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { SiteProvider } from "@/components/layout/site-context";
import { PageSkeleton } from "@/components/skeletons";
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
    return (
      <main className="mx-auto w-full max-w-5xl flex-1 p-6">
        <PageSkeleton />
      </main>
    );
  }
  if (isError || !data) {
    return null; // redirecting
  }
  return (
    <SiteProvider>
      <div className="flex min-h-svh w-full">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader />
          <UsageBanner />
          <main className="flex-1 p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </SiteProvider>
  );
}
