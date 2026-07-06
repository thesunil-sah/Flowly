"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Field, FormError, PasswordField } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useDeleteAccount } from "@/hooks/useAccount";

// Irreversible: wipes every site's analytics + all account data. Guarded by a
// typed "DELETE" confirmation and (for password accounts) the current password.

const CONFIRM_WORD = "DELETE";

export function DeleteAccountDialog({ hasPassword }: { hasPassword: boolean }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const router = useRouter();
  const del = useDeleteAccount();

  const confirmed = confirm.trim().toUpperCase() === CONFIRM_WORD;

  function onOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setPassword("");
      setConfirm("");
      del.reset();
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!confirmed) return;
    del.mutate(
      { password: hasPassword ? password : undefined },
      {
        onSuccess: () => {
          toast.success("Your account has been deleted");
          router.replace("/sign-in");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">
          Delete account
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete account</DialogTitle>
          <DialogDescription>
            This permanently deletes your account, every site, and all of its analytics data. This
            cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {hasPassword ? (
            <PasswordField
              id="delete-password"
              label="Current password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          ) : null}
          <Field
            id="delete-confirm"
            label={`Type ${CONFIRM_WORD} to confirm`}
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="off"
            placeholder={CONFIRM_WORD}
          />
          {del.isError ? <FormError>{del.error.message}</FormError> : null}
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button type="button" variant="ghost" size="sm">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" variant="destructive" size="sm" disabled={!confirmed || del.isPending}>
              {del.isPending ? "Deleting…" : "Delete account"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
