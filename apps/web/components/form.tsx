"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

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
      <span className="text-sm text-gray-600">{label}</span>
      <input
        {...props}
        className="w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-black"
      />
    </label>
  );
}

export function Submit({ children, pending }: { children: ReactNode; pending: boolean }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
    >
      {pending ? "…" : children}
    </button>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  return <p className="text-sm text-red-600">{children}</p>;
}

export function DevCodeHint({ code }: { code: string | null | undefined }) {
  if (!code) return null;
  return (
    <p className="rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">
      Dev mode — your code is <span className="font-mono font-semibold">{code}</span>
    </p>
  );
}
