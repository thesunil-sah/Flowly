"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { MessageCircle, Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAssistant } from "@/hooks/useAssistant";
import { FAQ } from "@/content/faq";
import { cn } from "@/lib/utils";

// Floating support chatbot (Phase F7), marketing pages only. Hardcoded FAQ
// intents answer instantly server-side; unmatched questions fall through to the
// rate-limited AI endpoint (or a contact fallback). Suggested prompts are the
// FAQ single source (content/faq.ts), so the chips can't drift from the answers.

type ChatMessage = { role: "user" | "bot"; text: string };

const GREETING =
  "Hi! I'm the Flowly assistant. Ask me about pricing, privacy, features, or how to get started.";
const SUGGESTIONS = FAQ.slice(0, 4).map((f) => f.question);

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "bot", text: GREETING }]);
  const assistant = useAssistant();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Keep the newest message in view (DOM side effect, not state).
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  function send(text: string) {
    const message = text.trim();
    if (!message || assistant.isPending) return;
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setInput("");
    assistant.mutate(message, {
      onSuccess: (res) => setMessages((prev) => [...prev, { role: "bot", text: res.reply }]),
      onError: () =>
        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            text: "Sorry — something went wrong. Please try again, or reach us at /contact.",
          },
        ]),
    });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <>
      {/* Panel */}
      {open ? (
        <div className="fixed right-4 bottom-20 z-50 flex h-[28rem] w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-card sm:right-6 sm:bottom-24">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-primary">
                <MessageCircle className="size-3.5" aria-hidden />
              </span>
              <span className="text-sm font-semibold">Flowly assistant</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                    m.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground",
                  )}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {assistant.isPending ? (
              <div className="flex justify-start">
                <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                  Typing…
                </div>
              </div>
            ) : null}

            {messages.length === 1 ? (
              <div className="flex flex-col gap-1.5 pt-1">
                {SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="rounded-md border border-border px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-border p-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              aria-label="Message"
              maxLength={1000}
              className="h-9"
            />
            <Button type="submit" size="icon" className="size-9 shrink-0" disabled={assistant.isPending} aria-label="Send">
              <Send className="size-4" aria-hidden />
            </Button>
          </form>
        </div>
      ) : null}

      {/* Toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close chat" : "Open chat"}
        aria-expanded={open}
        className="fixed right-4 bottom-4 z-50 flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-card transition-transform hover:scale-105 motion-reduce:transition-none sm:right-6 sm:bottom-6"
      >
        {open ? <X className="size-5" aria-hidden /> : <MessageCircle className="size-5" aria-hidden />}
      </button>
    </>
  );
}
