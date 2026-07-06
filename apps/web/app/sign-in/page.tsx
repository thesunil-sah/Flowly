"use client";

import { Mail } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { AuthCard, AuthLayout } from "@/components/auth/auth-shell";
import { Field, FormError, PasswordField, SubmitButton, SuccessNote } from "@/components/auth/fields";
import { SocialButtons } from "@/components/SocialButtons";
import { useLogin } from "@/hooks/useAuth";
import { postAuthPath } from "@/lib/post-auth";

function SignIn() {
  const router = useRouter();
  const params = useSearchParams();
  const justVerified = params.get("verified") === "1";
  const login = useLogin();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    login.mutate(
      { identifier, password, remember },
      { onSuccess: async () => router.push(await postAuthPath()) },
    );
  }

  return (
    <AuthLayout>
      <AuthCard
        tab="sign-in"
        title="Welcome back"
        subtitle="Sign in to continue to your account"
        footer={
          <>
            Don&apos;t have an account?{" "}
            <Link href="/sign-up" className="font-medium text-primary hover:underline">
              Sign up
            </Link>
          </>
        }
      >
        {justVerified ? <SuccessNote>Email verified — please sign in.</SuccessNote> : null}
        <form onSubmit={onSubmit} className="space-y-4">
          <Field
            id="identifier"
            label="Email or username"
            icon={Mail}
            placeholder="you@example.com"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            autoComplete="username"
          />
          <PasswordField
            id="password"
            label="Password"
            placeholder="••••••••••••"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            labelEnd={
              <Link href="/forgot-password" className="text-sm text-primary hover:underline">
                Forgot password?
              </Link>
            }
          />
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="size-4 rounded accent-primary"
            />
            Remember me
          </label>

          {login.isError ? <FormError>{login.error.message}</FormError> : null}
          <SubmitButton pending={login.isPending}>Sign in</SubmitButton>
        </form>
        <SocialButtons />
      </AuthCard>
    </AuthLayout>
  );
}

export default function SignInPage() {
  // useSearchParams requires a Suspense boundary during prerender.
  return (
    <Suspense>
      <SignIn />
    </Suspense>
  );
}
