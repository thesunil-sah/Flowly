"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Account, type Identity, type MessageResponse } from "@/lib/api";
import { clearTokens } from "@/lib/auth";

// Account self-service settings (Phase F3). Mutations that change the account
// write the fresh AccountOut straight into the ["me"] cache so the header + page
// reflect it without a refetch; the delete hook tears the client session down.

function post<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
}

/** The account's linked OAuth identities (google / github). */
export function useIdentities() {
  return useQuery({
    queryKey: ["identities"],
    queryFn: () => apiFetch<Identity[]>("/account/identities"),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (v: { current_password: string; new_password: string }) =>
      post<void>("/account/change-password", v),
  });
}

/** Step 1: request an email change — sends a verification code to the new address. */
export function useRequestEmailChange() {
  return useMutation({
    mutationFn: (v: { new_email: string; password?: string }) =>
      post<MessageResponse>("/account/change-email", v),
  });
}

/** Step 2: confirm the code and switch the account email. */
export function useVerifyEmailChange() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { new_email: string; code: string }) =>
      post<Account>("/account/verify-email-change", v),
    onSuccess: (account) => qc.setQueryData(["me"], account),
  });
}

export function useEmailPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { email_opt_out: boolean }) =>
      apiFetch<Account>("/account/email-preferences", {
        method: "PUT",
        body: JSON.stringify(v),
      }),
    onSuccess: (account) => qc.setQueryData(["me"], account),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { password?: string }) => post<void>("/account/delete", v),
    onSuccess: () => {
      clearTokens();
      qc.clear();
    },
  });
}
