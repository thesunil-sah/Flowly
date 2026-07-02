"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { AuthShell, ErrorText, Field, Submit } from "@/components/form";
import { SocialButtons } from "@/components/SocialButtons";
import { useLogin } from "@/hooks/useAuth";

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
      { onSuccess: () => router.push("/dashboard") },
    );
  }

  return (
    <AuthShell title="Sign in">
      {justVerified ? (
        <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700">
          Email verified — please sign in.
        </p>
      ) : null}
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Email or username"
          required
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          autoComplete="username"
        />
        <Field
          label="Password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        <div className="flex items-center justify-between text-sm text-gray-600">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            Remember me
          </label>
          <Link href="/forgot-password" className="underline">
            Forgot password?
          </Link>
        </div>

        {login.isError ? <ErrorText>{login.error.message}</ErrorText> : null}
        <Submit pending={login.isPending}>Sign in</Submit>
      </form>
      <SocialButtons />
      <p className="text-sm text-gray-600">
        Need an account?{" "}
        <Link href="/sign-up" className="underline">
          Sign up
        </Link>
      </p>
    </AuthShell>
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
