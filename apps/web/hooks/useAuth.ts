"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiFetch,
  type Account,
  type MessageResponse,
  type ResetTokenResponse,
  type TokenResponse,
} from "@/lib/api";
import { clearTokens, setTokens } from "@/lib/auth";

function post<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
}

// --- Signup + email verification -----------------------------------------
export function useSignup() {
  return useMutation({
    mutationFn: (v: { username: string; email: string; password: string }) =>
      post<MessageResponse>("/auth/signup", v),
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (v: { email: string; code: string }) =>
      post<MessageResponse>("/auth/verify-email", v),
  });
}

export function useResendCode() {
  return useMutation({
    mutationFn: (v: { email: string }) => post<MessageResponse>("/auth/resend-code", v),
  });
}

// --- Login ----------------------------------------------------------------
export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { identifier: string; password: string; remember: boolean }) => {
      const tokens = await post<TokenResponse>("/auth/login", {
        identifier: v.identifier,
        password: v.password,
      });
      setTokens(tokens.access_token, tokens.refresh_token, v.remember);
      return tokens;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

// --- Password reset -------------------------------------------------------
export function useForgotPassword() {
  return useMutation({
    mutationFn: (v: { email: string }) => post<MessageResponse>("/auth/forgot-password", v),
  });
}

export function useVerifyResetCode() {
  return useMutation({
    mutationFn: (v: { email: string; code: string }) =>
      post<ResetTokenResponse>("/auth/verify-reset-code", v),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (v: { reset_token: string; password: string }) =>
      post<MessageResponse>("/auth/reset-password", v),
  });
}

// --- Session --------------------------------------------------------------
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Account>("/auth/me"),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return async () => {
    try {
      await apiFetch<void>("/auth/logout", { method: "POST" });
    } catch {
      // best-effort; clear the client regardless
    }
    clearTokens();
    qc.clear();
  };
}
