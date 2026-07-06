"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthShell, DevCodeHint, ErrorText, Field, Submit } from "@/components/form";
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

  if (step === "code") {
    return (
      <AuthShell title="Enter reset code">
        <p className="text-sm text-muted-foreground">
          If an account exists for <span className="font-medium">{email}</span>, a code was sent.
        </p>
        <DevCodeHint code={devCode} />
        <form onSubmit={onSubmitCode} className="space-y-4">
          <Field
            label="Reset code"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          {verify.isError ? <ErrorText>{verify.error.message}</ErrorText> : null}
          <Submit pending={verify.isPending}>Verify code</Submit>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Forgot password">
      <p className="text-sm text-muted-foreground">Enter your email and we&apos;ll send a reset code.</p>
      <form onSubmit={onSubmitEmail} className="space-y-4">
        <Field
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        {forgot.isError ? <ErrorText>{forgot.error.message}</ErrorText> : null}
        <Submit pending={forgot.isPending}>Send reset code</Submit>
      </form>
      <p className="text-sm text-muted-foreground">
        <Link href="/sign-in" className="underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
