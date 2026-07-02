"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthShell, DevCodeHint, ErrorText, Field, Submit } from "@/components/form";
import { SocialButtons } from "@/components/SocialButtons";
import { useResendCode, useSignup, useVerifyEmail } from "@/hooks/useAuth";

export default function SignUpPage() {
  const router = useRouter();
  const signup = useSignup();
  const verify = useVerifyEmail();
  const resend = useResendCode();

  const [step, setStep] = useState<"form" | "code">("form");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [remember, setRemember] = useState(false);
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [mismatch, setMismatch] = useState(false);

  function onSubmitForm(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    signup.mutate(
      { username, email, password },
      {
        onSuccess: (data) => {
          setDevCode(data.dev_code);
          setStep("code");
        },
      },
    );
  }

  function onSubmitCode(e: FormEvent) {
    e.preventDefault();
    verify.mutate(
      { email, code },
      { onSuccess: () => router.push("/sign-in?verified=1") },
    );
  }

  if (step === "code") {
    return (
      <AuthShell title="Check your email">
        <p className="text-sm text-gray-600">
          We sent a 6-digit code to <span className="font-medium">{email}</span>.
        </p>
        <DevCodeHint code={devCode} />
        <form onSubmit={onSubmitCode} className="space-y-4">
          <Field
            label="Verification code"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          {verify.isError ? <ErrorText>{verify.error.message}</ErrorText> : null}
          <Submit pending={verify.isPending}>Verify email</Submit>
        </form>
        <button
          type="button"
          onClick={() => resend.mutate({ email }, { onSuccess: (d) => setDevCode(d.dev_code) })}
          disabled={resend.isPending}
          className="text-sm text-gray-600 underline disabled:opacity-50"
        >
          Resend code
        </button>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your account">
      <form onSubmit={onSubmitForm} className="space-y-4">
        <Field
          label="Username"
          required
          minLength={3}
          maxLength={32}
          pattern="[A-Za-z0-9_]+"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <Field
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <Field
          label="Password"
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        <Field
          label="Confirm password"
          type="password"
          required
          minLength={8}
          maxLength={128}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          Remember me
        </label>

        {mismatch ? <ErrorText>Passwords do not match.</ErrorText> : null}
        {signup.isError ? <ErrorText>{signup.error.message}</ErrorText> : null}

        <Submit pending={signup.isPending}>Sign up</Submit>
      </form>
      <SocialButtons />
      <p className="text-sm text-gray-600">
        Already have an account?{" "}
        <Link href="/sign-in" className="underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
