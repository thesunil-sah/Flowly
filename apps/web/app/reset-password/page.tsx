"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore, type FormEvent } from "react";

import { AuthShell, ErrorText, Field, Submit } from "@/components/form";
import { useResetPassword } from "@/hooks/useAuth";
import { RESET_TOKEN_KEY } from "@/lib/constants";

// SSR-safe read of the client-only reset token: null on the server, the stored
// value on the client — no effect, no hydration mismatch.
function useResetToken(): string | null {
  return useSyncExternalStore(
    () => () => {},
    () => window.sessionStorage.getItem(RESET_TOKEN_KEY),
    () => null,
  );
}

export default function ResetPasswordPage() {
  const router = useRouter();
  const reset = useResetPassword();

  const token = useResetToken();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    if (!token) return;
    reset.mutate(
      { reset_token: token, password },
      {
        onSuccess: () => {
          window.sessionStorage.removeItem(RESET_TOKEN_KEY);
          router.push("/sign-in?verified=1");
        },
      },
    );
  }

  if (token === null) {
    return (
      <AuthShell title="Reset password">
        <p className="text-sm text-muted-foreground">
          No active reset request.{" "}
          <Link href="/forgot-password" className="underline">
            Start over
          </Link>
          .
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Set a new password">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="New password"
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        <Field
          label="Confirm new password"
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
        />
        {mismatch ? <ErrorText>Passwords do not match.</ErrorText> : null}
        {reset.isError ? <ErrorText>{reset.error.message}</ErrorText> : null}
        <Submit pending={reset.isPending}>Reset password</Submit>
      </form>
    </AuthShell>
  );
}
