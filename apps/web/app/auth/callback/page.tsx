"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { AuthCard, AuthLayout } from "@/components/auth/auth-shell";
import { FormError } from "@/components/auth/fields";
import { setTokens } from "@/lib/auth";
import { postAuthPath } from "@/lib/post-auth";

// The OAuth callback lands here with tokens (or an error) in the URL fragment,
// e.g. #access_token=…&refresh_token=… . Read it SSR-safely.
function useHash(): string {
  return useSyncExternalStore(
    () => () => {},
    () => window.location.hash,
    () => "",
  );
}

export default function OAuthCallbackPage() {
  const router = useRouter();
  const params = new URLSearchParams(useHash().replace(/^#/, ""));
  const access = params.get("access_token");
  const refresh = params.get("refresh_token");
  const error = params.get("error");

  useEffect(() => {
    if (access && refresh) {
      setTokens(access, refresh, true); // social logins persist across restarts
      // First-time OAuth accounts have no sites — send them to add-first-site.
      postAuthPath().then((path) => router.replace(path));
    }
  }, [access, refresh, router]);

  if (error) {
    return (
      <AuthLayout>
        <AuthCard
          title="Sign-in failed"
          footer={
            <Link href="/sign-in" className="font-medium text-primary hover:underline">
              Back to sign in
            </Link>
          }
        >
          <FormError>{error}</FormError>
        </AuthCard>
      </AuthLayout>
    );
  }

  if (access && refresh) {
    return (
      <AuthLayout>
        <AuthCard title="Signing you in…">
          <div className="flex justify-center py-4">
            <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
          </div>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard title="Nothing to do here">
        <p className="text-sm text-muted-foreground">
          <Link href="/sign-in" className="font-medium text-primary hover:underline">
            Go to sign in
          </Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
