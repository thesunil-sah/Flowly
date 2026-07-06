"use client";

import { Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthCard, AuthLayout } from "@/components/auth/auth-shell";
import { DevCodeHint, Field, FormError, SubmitButton } from "@/components/auth/fields";
import { useForgotPassword, useVerifyResetCode } from "@/hooks/useAuth";
import { RESET_TOKEN_KEY } from "@/lib/constants";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const forgot = useForgotPassword();
  const verify = useVerifyResetCode();

  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);

  function onSubmitEmail(e: FormEvent) {
    e.preventDefault();
    forgot.mutate(
      { email },
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
      {
        onSuccess: (data) => {
          window.sessionStorage.setItem(RESET_TOKEN_KEY, data.reset_token);
          router.push("/reset-password");
        },
      },
    );
  }

  const backToSignIn = (
    <Link href="/sign-in" className="font-medium text-primary hover:underline">
      Back to sign in
    </Link>
  );

  if (step === "code") {
    return (
      <AuthLayout>
        <AuthCard
          title="Enter reset code"
          subtitle={`If an account exists for ${email}, a code was sent.`}
          footer={backToSignIn}
        >
          <DevCodeHint code={devCode} />
          <form onSubmit={onSubmitCode} className="space-y-4">
            <Field
              id="code"
              label="Reset code"
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
            <SubmitButton pending={verify.isPending}>Verify code</SubmitButton>
          </form>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard
        title="Forgot password"
        subtitle="Enter your email and we'll send a reset code."
        footer={backToSignIn}
      >
        <form onSubmit={onSubmitEmail} className="space-y-4">
          <Field
            id="email"
            label="Email address"
            type="email"
            icon={Mail}
            placeholder="you@example.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          {forgot.isError ? <FormError>{forgot.error.message}</FormError> : null}
          <SubmitButton pending={forgot.isPending}>Send reset code</SubmitButton>
        </form>
      </AuthCard>
    </AuthLayout>
  );
}
