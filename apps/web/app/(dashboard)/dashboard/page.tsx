"use client";

import { useRouter } from "next/navigation";

import { useLogout, useMe } from "@/hooks/useAuth";

export default function DashboardPage() {
  const router = useRouter();
  const { data } = useMe();
  const logout = useLogout();

  async function onLogout() {
    await logout();
    router.replace("/sign-in");
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Welcome{data ? `, ${data.email}` : ""}</h1>
      <p className="text-gray-600">
        Plan: {data?.plan ?? "…"} · Status: {data?.status ?? "…"}
      </p>
      <button onClick={onLogout} className="rounded border border-gray-300 px-4 py-2">
        Log out
      </button>
    </main>
  );
}
