"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

// Support chatbot (Phase F7): posts a message to the public, rate-limited
// /assistant/chat endpoint (hardcoded FAQ intents + AI fallback) and returns
// the reply. No auth — it's a marketing-page widget.
export type AssistantReply = { reply: string; source: "faq" | "ai" | "fallback" };

export function useAssistant() {
  return useMutation({
    mutationFn: (message: string) =>
      apiFetch<AssistantReply>("/assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
  });
}
