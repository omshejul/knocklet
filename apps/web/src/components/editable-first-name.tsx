"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Pencil } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appear } from "@/lib/motion";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export function EditableFirstName({
  personId,
  personName,
  firstName,
  onEditing,
  onSaved,
}: {
  personId: string;
  personName: string;
  firstName: string;
  onEditing: () => void;
  onSaved: (firstName: string) => void;
}) {
  const reducedMotion = useReducedMotion();
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(firstName);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function saveFirstName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextFirstName = value.trim();
    if (!nextFirstName) {
      setError("First name is required.");
      return;
    }
    if (nextFirstName === firstName) {
      setIsEditing(false);
      setError("");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const response = await fetch(apiUrl + "/people/" + personId, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ first_name: nextFirstName }),
      });
      const data = (await response.json()) as {
        first_name?: string;
        detail?: string;
      };
      if (!response.ok || !data.first_name) {
        throw new Error(data.detail ?? "First name could not be saved.");
      }
      setValue(data.first_name);
      setIsEditing(false);
      onSaved(data.first_name);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "First name could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      {isEditing ? (
        <motion.form
          key="edit"
          {...appear(reducedMotion)}
          className="flex flex-wrap items-center gap-1"
          onSubmit={saveFirstName}
        >
          <label htmlFor={`first-name-${personId}`} className="sr-only">
            First name for {personName}
          </label>
          <Input
            id={`first-name-${personId}`}
            value={value}
            maxLength={255}
            autoFocus
            disabled={isSaving}
            aria-invalid={Boolean(error)}
            className="w-32"
            onChange={(event) => {
              setValue(event.target.value);
              setError("");
            }}
          />
          <Button type="submit" size="xs" loading={isSaving}>
            Save
          </Button>
          <Button
            type="button"
            size="xs"
            variant="ghost"
            disabled={isSaving}
            onClick={() => {
              setValue(firstName);
              setError("");
              setIsEditing(false);
            }}
          >
            Cancel
          </Button>
          {error ? (
            <p
              className="basis-full whitespace-normal text-xs text-destructive"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </motion.form>
      ) : (
        <motion.button
          key="display"
          {...appear(reducedMotion)}
          type="button"
          className="-mx-2 inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          aria-label={`Edit first name for ${personName}`}
          onClick={() => {
            onEditing();
            setValue(firstName);
            setError("");
            setIsEditing(true);
          }}
        >
          {firstName}
          <Pencil className="size-3 text-muted-foreground" aria-hidden="true" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
