// Contact destinations for the keyless (no email provider) contact page.
// Both are client-side handoffs: the visitor's own mail app / WhatsApp sends the
// message to us, so no API key or server send is involved.

/** Inbox that the "Email us" mailto button is addressed to. */
export const CONTACT_EMAIL: string = "aisecure302@gmail.com";

/**
 * WhatsApp click-to-chat number in FULL international format, digits only —
 * no +, spaces, or dashes (e.g. "919876543210"). Empty string hides the
 * WhatsApp button. Set this to enable "Chat on WhatsApp".
 */
export const WHATSAPP_NUMBER: string = "447771808649";
