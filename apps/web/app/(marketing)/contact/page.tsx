"use client";

import { useState } from "react";
import { AtSign, Mail, MessageCircle, User } from "lucide-react";

import { Field } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CONTACT_EMAIL, WHATSAPP_NUMBER } from "@/lib/contact";

// Keyless contact page (F6): no server send, no email provider. The visitor's
// own mail app (mailto:) or WhatsApp (wa.me) delivers the message to us, so it
// works with zero credentials. The /contact backend endpoint stays in place for
// when a real email provider is configured.

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const from = [name && `From: ${name}`, email && `<${email}>`].filter(Boolean).join(" ");
  const body = [message, from && `\n${from}`].filter(Boolean).join("\n");

  const mailtoHref =
    `mailto:${CONTACT_EMAIL}` +
    `?subject=${encodeURIComponent(name ? `Flowly contact — ${name}` : "Flowly contact")}` +
    `&body=${encodeURIComponent(body)}`;

  const waText = [
    "Hi Flowly,",
    name && `I'm ${name}.`,
    message,
    email && `(${email})`,
  ]
    .filter(Boolean)
    .join(" ");
  const whatsappHref = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(waText)}`;

  const ready = name.trim() !== "" && message.trim() !== "";

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col gap-6 px-4 py-16 sm:px-6 lg:py-24">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Contact us</h1>
        <p className="text-muted-foreground">
          Questions, feedback, or a feature request? Fill this in and send it your way — it opens
          your email or WhatsApp, pre-filled, and comes straight to us.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <Field
          id="name"
          label="Name"
          icon={User}
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />
        <Field
          id="email"
          label="Your email"
          icon={AtSign}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
        <div className="space-y-1.5">
          <label htmlFor="message" className="text-sm font-medium">
            Message
          </label>
          <Textarea
            id="message"
            rows={5}
            maxLength={5000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="How can we help?"
          />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button asChild className="gap-2" aria-disabled={!ready}>
            <a
              href={ready ? mailtoHref : undefined}
              onClick={(e) => {
                if (!ready) e.preventDefault();
              }}
            >
              <Mail className="size-4" aria-hidden />
              Send via email
            </a>
          </Button>

          {WHATSAPP_NUMBER ? (
            <Button asChild variant="outline" className="gap-2" aria-disabled={!ready}>
              <a
                href={ready ? whatsappHref : undefined}
                target="_blank"
                rel="noreferrer noopener"
                onClick={(e) => {
                  if (!ready) e.preventDefault();
                }}
              >
                <MessageCircle className="size-4 text-success" aria-hidden />
                Chat on WhatsApp
              </a>
            </Button>
          ) : null}
        </div>
        {!ready ? (
          <p className="text-xs text-muted-foreground">
            Add your name and a message to enable sending.
          </p>
        ) : null}

        <p className="text-sm text-muted-foreground">
          Prefer plain email? Write to{" "}
          <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
            {CONTACT_EMAIL}
          </a>
          .
        </p>
      </div>
    </div>
  );
}
