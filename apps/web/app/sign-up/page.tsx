"use client";

import { AtSign, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthCard, AuthLayout } from "@/components/auth/auth-shell";
import {
  DevCodeHint,
  Field,
  FormError,
  PasswordField,
  SubmitButton,
} from "@/components/auth/fields";
import { SocialButtons } from "@/components/SocialButtons";
import { useResendCode, useSignup, useVerifyEmail } from "@/hooks/useAuth";

type FieldErrors = Partial<Record<"username" | "email" | "password" | "confirm", string>>;

const USERNAME_RE = /^[A-Za-z0-9_]{3,32}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(v: { username: string; email: string; password: string; confirm: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (v.username && !USERNAME_RE.test(v.username))
    errors.username = "3–32 characters: letters, numbers, underscores.";
  if (v.email && !EMAIL_RE.test(v.email)) errors.email = "Enter a valid email address.";
  if (v.password && v.password.length < 8) errors.password = "At least 8 characters.";
  if (v.confirm && v.confirm !== v.password) errors.confirm = "Passwords do not match.";
  return errors;
}

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
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});

  // Inline validation (F2): re-check touched fields on every blur.
  function onBlur() {
    setErrors(validate({ username, email, password, confirm }));
  }

  function onSubmitForm(e: FormEvent) {
    e.preventDefault();
    const found = validate({ username, email, password, confirm });
    if (!username) found.username = "Pick a username.";
    if (!email) found.email = "Enter your email.";
    if (!password) found.password = "Choose a password (8+ characters).";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
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
      // The account has no sites yet — after signing in, postAuthPath routes
      // them into the add-first-site flow.
      { onSuccess: () => router.push("/sign-in?verified=1") },
    );
  }

  if (step === "code") {
    return (
      <AuthLayout>
        <AuthCard
          title="Check your email"
          subtitle={`We sent a 6-digit code to ${email}.`}
          footer={
            <button
              type="button"
              onClick={() => resend.mutate({ email }, { onSuccess: (d) => setDevCode(d.dev_code) })}
              disabled={resend.isPending}
              className="font-medium text-primary hover:underline disabled:opacity-50"
            >
              Resend code
            </button>
          }
        >
          <DevCodeHint code={devCode} />
          <form onSubmit={onSubmitCode} className="space-y-4">
            <Field
              id="code"
              label="Verification code"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              className="text-center font-mono text-lg tracking-[0.4em]"
              autoComplete="one-time-code"
            />
            {verify.isError ? <FormError>{verify.error.message}</FormError> : null}
            <SubmitButton pending={verify.isPending}>Verify email</SubmitButton>
          </form>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard
        tab="sign-up"
        title="Create your account"
        subtitle="Free for your first 1,000 pageviews a month — no card required"
        footer={
          <>
            Already have an account?{" "}
            <Link href="/sign-in" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </>
        }
      >
        <form onSubmit={onSubmitForm} className="space-y-4" noValidate>
          <Field
            id="username"
            label="Username"
            icon={AtSign}
            placeholder="yourname"
            error={errors.username}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onBlur={onBlur}
            autoComplete="username"
          />
          <Field
            id="email"
            label="Email address"
            type="email"
            icon={Mail}
            placeholder="you@example.com"
            error={errors.email}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={onBlur}
            autoComplete="email"
          />
          <PasswordField
            id="password"
            label="Password"
            placeholder="8+ characters"
            error={errors.password}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onBlur={onBlur}
            autoComplete="new-password"
          />
          <PasswordField
            id="confirm"
            label="Confirm password"
            placeholder="Repeat your password"
            error={errors.confirm}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            onBlur={onBlur}
            autoComplete="new-password"
          />

          {signup.isError ? <FormError>{signup.error.message}</FormError> : null}
          <SubmitButton pending={signup.isPending}>Create account</SubmitButton>
        </form>
        <SocialButtons />
      </AuthCard>
    </AuthLayout>
  );
}
