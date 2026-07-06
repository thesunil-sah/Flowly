"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

// Public contact-form submission (F6). `company` is the honeypot field — always
// sent (empty for humans); the backend drops the message if it's filled.
export type ContactInput = {
  name: string;
  email: string;
  message: string;
  company: string;
};

export function useContact() {
  return useMutation({
    mutationFn: (v: ContactInput) =>
      apiFetch<void>("/contact", { method: "POST", body: JSON.stringify(v) }),
  });
}
