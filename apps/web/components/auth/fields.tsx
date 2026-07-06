"use client";

import { ArrowRight, Eye, EyeOff, Loader2, Lock, type LucideIcon } from "lucide-react";
import { useState, type InputHTMLAttributes, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// F2 form primitives — icon-inset inputs with inline validation states,
// replacing the plain Field/Submit set that lived in components/form.tsx.

type FieldProps = {
  id: string;
  label: string;
  icon?: LucideIcon;
  /** Inline validation message; presence flips the input to its invalid state. */
  error?: string | null;
  /** Rendered on the label row's right side (e.g. a "Forgot password?" link). */
  labelEnd?: ReactNode;
  /** Rendered inside the input on the right (e.g. the password eye toggle). */
  trailing?: ReactNode;
} & InputHTMLAttributes<HTMLInputElement>;

export function Field({
  id,
  label,
  icon: Icon,
  error,
  labelEnd,
  trailing,
  className,
  ...props
}: FieldProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {labelEnd}
      </div>
      <div className="relative">
        {Icon ? (
          <Icon
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground/70"
            aria-hidden
          />
        ) : null}
        <Input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cn("h-10", Icon && "pl-9", trailing && "pr-10", className)}
          {...props}
        />
        {trailing}
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function PasswordField(props: Omit<FieldProps, "type" | "trailing">) {
  const [visible, setVisible] = useState(false);
  return (
    <Field
      icon={Lock}
      type={visible ? "text" : "password"}
      trailing={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground/70 transition-colors hover:text-foreground"
        >
          {visible ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
        </button>
      }
      {...props}
    />
  );
}

export function SubmitButton({ children, pending }: { children: ReactNode; pending: boolean }) {
  return (
    <Button type="submit" disabled={pending} className="h-10 w-full gap-2 text-sm">
      {pending ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        <>
          {children}
          <ArrowRight className="size-4 transition-transform group-hover/button:translate-x-0.5" aria-hidden />
        </>
      )}
    </Button>
  );
}

export function FormError({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
    >
      {children}
    </p>
  );
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm">{children}</p>
  );
}

export function DevCodeHint({ code }: { code: string | null | undefined }) {
  if (!code) return null;
  return (
    <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
      Dev mode — your code is <span className="font-mono font-semibold">{code}</span>
    </p>
  );
}
