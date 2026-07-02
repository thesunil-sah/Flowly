"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { AuthShell, ErrorText } from "@/components/form";
import { setTokens } from "@/lib/auth";

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
      router.replace("/dashboard");
    }
  }, [access, refresh, router]);

  if (error) {
    return (
      <AuthShell title="Sign-in failed">
        <ErrorText>{error}</ErrorText>
        <p className="text-sm text-gray-600">
          <Link href="/sign-in" className="underline">
            Back to sign in
          </Link>
        </p>
      </AuthShell>
    );
  }

  if (access && refresh) {
    return <AuthShell title="Signing you in…">{null}</AuthShell>;
  }

  return (
    <AuthShell title="Nothing to do here">
      <p className="text-sm text-gray-600">
        <Link href="/sign-in" className="underline">
          Go to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
