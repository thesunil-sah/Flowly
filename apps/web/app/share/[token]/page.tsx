"use client";

import { useParams } from "next/navigation";

import { PublicDashboard } from "@/components/public-dashboard/public-dashboard";

export default function SharePage() {
  const params = useParams<{ token: string }>();
  return <PublicDashboard token={params.token} />;
}
