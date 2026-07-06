"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Link2, Mail } from "lucide-react";
import { toast } from "sonner";

import { ChangeEmailDialog } from "@/components/settings/change-email-dialog";
import { DeleteAccountDialog } from "@/components/settings/delete-account-dialog";
import { FormError, PasswordField, SubmitButton } from "@/components/auth/fields";
import { PageSkeleton } from "@/components/skeletons";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Switch } from "@/components/ui/switch";
import { useIdentities, useChangePassword, useEmailPreferences } from "@/hooks/useAccount";
import { useMe } from "@/hooks/useAuth";
import type { Account } from "@/lib/api";

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="mb-4">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description ? <p className="mt-0.5 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border py-3 first:border-t-0 first:pt-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
      </div>
      {children}
    </div>
  );
}

function ProfileSection({ me }: { me: Account }) {
  return (
    <SectionCard title="Profile" description="Your account details.">
      <Row label="Username">
        <span className="text-sm">{me.username}</span>
      </Row>
      <Row label="Email">
        <div className="flex items-center gap-3">
          <span className="truncate text-sm">{me.email}</span>
          <ChangeEmailDialog currentEmail={me.email} hasPassword={me.has_password} />
        </div>
      </Row>
      <Row label="Plan">
        <Badge variant="secondary" className="capitalize">
          {me.plan}
        </Badge>
      </Row>
    </SectionCard>
  );
}

function PasswordSection({ hasPassword }: { hasPassword: boolean }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const change = useChangePassword();

  if (!hasPassword) {
    return (
      <SectionCard title="Password">
        <p className="text-sm text-muted-foreground">
          You sign in with a linked account, so there&apos;s no password to change.
        </p>
      </SectionCard>
    );
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          toast.success("Password updated");
          setCurrent("");
          setNext("");
          setConfirm("");
        },
      },
    );
  }

  return (
    <SectionCard title="Password" description="Change the password you use to sign in.">
      <form onSubmit={onSubmit} className="flex max-w-sm flex-col gap-4">
        <PasswordField
          id="current-password"
          label="Current password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
        />
        <PasswordField
          id="new-password"
          label="New password"
          required
          minLength={8}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
        />
        <PasswordField
          id="confirm-password"
          label="Confirm new password"
          required
          error={mismatch ? "Passwords don't match." : null}
          value={confirm}
          onChange={(e) => {
            setConfirm(e.target.value);
            setMismatch(false);
          }}
          autoComplete="new-password"
        />
        {change.isError ? <FormError>{change.error.message}</FormError> : null}
        <SubmitButton pending={change.isPending}>Update password</SubmitButton>
      </form>
    </SectionCard>
  );
}

function EmailPreferencesSection({ me }: { me: Account }) {
  const prefs = useEmailPreferences();
  // Present the positive framing (receive emails); the stored flag is the opt-OUT.
  const receiving = !me.email_opt_out;

  function onToggle(next: boolean) {
    prefs.mutate(
      { email_opt_out: !next },
      {
        onSuccess: () => toast.success(next ? "Subscribed to product emails" : "Unsubscribed"),
      },
    );
  }

  return (
    <SectionCard title="Email preferences">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium">Product tips &amp; weekly digest</p>
          <p className="text-sm text-muted-foreground">
            Occasional onboarding tips and your weekly traffic summary. Account and security emails
            are always sent.
          </p>
        </div>
        <Switch
          checked={receiving}
          onCheckedChange={onToggle}
          disabled={prefs.isPending}
          aria-label="Receive product emails"
        />
      </div>
    </SectionCard>
  );
}

const PROVIDER_ICON: Record<string, typeof Mail> = { google: Mail };

function LinkedAccountsSection() {
  const { data: identities, isLoading } = useIdentities();

  return (
    <SectionCard title="Linked accounts" description="Social logins connected to your account.">
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : identities && identities.length > 0 ? (
        <div className="flex flex-col">
          {identities.map((id) => {
            const Icon = PROVIDER_ICON[id.provider] ?? Link2;
            return (
              <Row key={id.id} label="">
                <div className="flex w-full items-center justify-between">
                  <span className="flex items-center gap-2 text-sm capitalize">
                    <Icon className="size-4 text-muted-foreground" aria-hidden />
                    {id.provider}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Connected {new Date(id.created_at).toLocaleDateString()}
                  </span>
                </div>
              </Row>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Link2}
          title="No linked accounts"
          description="Connect Google or GitHub from the sign-in page."
        />
      )}
    </SectionCard>
  );
}

function DangerZone({ hasPassword }: { hasPassword: boolean }) {
  return (
    <section className="rounded-lg border border-destructive/30 bg-card p-5 shadow-card">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-destructive">Danger zone</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Permanently delete your account and all of its analytics data.
        </p>
      </div>
      <DeleteAccountDialog hasPassword={hasPassword} />
    </section>
  );
}

export default function SettingsPage() {
  const { data: me, isLoading } = useMe();

  if (isLoading || !me) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <PageSkeleton />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <ProfileSection me={me} />
      <PasswordSection hasPassword={me.has_password} />
      <EmailPreferencesSection me={me} />
      <LinkedAccountsSection />
      <DangerZone hasPassword={me.has_password} />
    </div>
  );
}
