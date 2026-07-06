"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore, type FormEvent } from "react";

import { AuthCard, AuthLayout } from "@/components/auth/auth-shell";
import { FormError, PasswordField, SubmitButton } from "@/components/auth/fields";
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
      <AuthLayout>
        <AuthCard title="Reset password">
          <p className="text-sm text-muted-foreground">
            No active reset request.{" "}
            <Link href="/forgot-password" className="font-medium text-primary hover:underline">
              Start over
            </Link>
            .
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard title="Set a new password" subtitle="Choose a strong password you haven't used before.">
        <form onSubmit={onSubmit} className="space-y-4">
          <PasswordField
            id="password"
            label="New password"
            placeholder="8+ characters"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <PasswordField
            id="confirm"
            label="Confirm new password"
            placeholder="Repeat your password"
            required
            minLength={8}
            maxLength={128}
            error={mismatch ? "Passwords do not match." : null}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
          />
          {reset.isError ? <FormError>{reset.error.message}</FormError> : null}
          <SubmitButton pending={reset.isPending}>Reset password</SubmitButton>
        </form>
      </AuthCard>
    </AuthLayout>
  );
}
