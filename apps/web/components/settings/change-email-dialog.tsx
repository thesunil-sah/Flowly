"use client";

import { useState, type FormEvent } from "react";
import { AtSign } from "lucide-react";
import { toast } from "sonner";

import { DevCodeHint, Field, FormError, PasswordField, SubmitButton } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useRequestEmailChange, useVerifyEmailChange } from "@/hooks/useAccount";

// Two-step email change: request a code to the NEW address, then confirm it.
// Verifying the new address proves the user controls it before we switch.

export function ChangeEmailDialog({
  currentEmail,
  hasPassword,
}: {
  currentEmail: string;
  hasPassword: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<"request" | "verify">("request");
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);

  const request = useRequestEmailChange();
  const verify = useVerifyEmailChange();

  function reset() {
    setStep("request");
    setNewEmail("");
    setPassword("");
    setCode("");
    setDevCode(null);
    request.reset();
    verify.reset();
  }

  function onOpenChange(next: boolean) {
    setOpen(next);
    if (!next) reset();
  }

  function onRequest(e: FormEvent) {
    e.preventDefault();
    request.mutate(
      { new_email: newEmail, password: hasPassword ? password : undefined },
      {
        onSuccess: (res) => {
          setDevCode(res.dev_code);
          setStep("verify");
        },
      },
    );
  }

  function onVerify(e: FormEvent) {
    e.preventDefault();
    verify.mutate(
      { new_email: newEmail, code },
      {
        onSuccess: () => {
          toast.success("Email updated");
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Change
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change email</DialogTitle>
          <DialogDescription>
            {step === "request"
              ? `Currently ${currentEmail}. We'll send a code to your new address to confirm it.`
              : `Enter the 6-digit code we sent to ${newEmail}.`}
          </DialogDescription>
        </DialogHeader>

        {step === "request" ? (
          <form onSubmit={onRequest} className="flex flex-col gap-4">
            <Field
              id="new-email"
              label="New email"
              icon={AtSign}
              type="email"
              required
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              autoComplete="email"
            />
            {hasPassword ? (
              <PasswordField
                id="current-password-email"
                label="Current password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            ) : null}
            {request.isError ? <FormError>{request.error.message}</FormError> : null}
            <SubmitButton pending={request.isPending}>Send code</SubmitButton>
          </form>
        ) : (
          <form onSubmit={onVerify} className="flex flex-col gap-4">
            <DevCodeHint code={devCode} />
            <Field
              id="email-change-code"
              label="Verification code"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="one-time-code"
              placeholder="000000"
            />
            {verify.isError ? <FormError>{verify.error.message}</FormError> : null}
            <SubmitButton pending={verify.isPending}>Confirm new email</SubmitButton>
            <DialogClose asChild>
              <Button type="button" variant="ghost" size="sm">
                Cancel
              </Button>
            </DialogClose>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
