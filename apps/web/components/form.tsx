"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {children}
      </div>
    </main>
  );
}

export function Field({
  label,
  ...props
}: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Input {...props} />
    </label>
  );
}

export function Submit({ children, pending }: { children: ReactNode; pending: boolean }) {
  return (
    <Button type="submit" disabled={pending} className="w-full">
      {pending ? "…" : children}
    </Button>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  return <p className="text-sm text-destructive">{children}</p>;
}

export function DevCodeHint({ code }: { code: string | null | undefined }) {
  if (!code) return null;
  return (
    <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
      Dev mode — your code is <span className="font-mono font-semibold">{code}</span>
    </p>
  );
}
