"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";

type MessageTemplate = {
  body: string;
  auto_send_enabled: boolean;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export function MessagesPanel() {
  const [body, setBody] = useState("");
  const [autoSend, setAutoSend] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(apiUrl + "/message-template", { cache: "no-store" })
      .then(async (response) => {
        if (response.status === 204) return null;
        if (!response.ok) throw new Error("Template could not be loaded.");
        return (await response.json()) as MessageTemplate;
      })
      .then((template) => {
        if (!active || !template) return;
        setBody(template.body);
        setAutoSend(template.auto_send_enabled);
      })
      .catch((loadError: Error) => {
        if (active) setError(loadError.message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function saveTemplate() {
    setIsSaving(true);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/message-template", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Follow-up",
          body,
          auto_send_enabled: autoSend,
        }),
      });
      const data = (await response.json()) as MessageTemplate & { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? "Template could not be saved.");
      }
      setBody(data.body);
      setAutoSend(data.auto_send_enabled);
      setConfirmation("Template saved.");
    } catch (saveError) {
      setError(
        saveError instanceof Error ? saveError.message : "Template could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card className="mt-5 shadow-xl shadow-black/40">
      <CardContent className="space-y-4 px-4 sm:px-5">
        <div>
          <label htmlFor="message-template" className="text-sm font-bold">
            Follow-up template
          </label>
          <textarea
            id="message-template"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            disabled={isLoading || isSaving}
            rows={6}
            placeholder="Thanks for connecting, {first_name}."
            className="mt-2 flex min-h-32 w-full resize-y rounded-xl border border-input bg-transparent px-3 py-2 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <p className="mt-1.5 text-xs text-muted-foreground">
            Use {"{first_name}"}. Applies to requests approved after saving.
          </p>
        </div>

        <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
          <Checkbox
            checked={autoSend}
            onCheckedChange={setAutoSend}
            disabled={isLoading || isSaving}
            aria-label="Send automatically after acceptance"
          />
          Send automatically after acceptance
        </label>

        {confirmation ? (
          <p className="text-sm text-success" role="status" aria-live="polite">
            {confirmation}
          </p>
        ) : null}
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <Button
          type="button"
          onClick={saveTemplate}
          disabled={isLoading || isSaving || body.trim().length === 0}
          aria-busy={isSaving}
          className="min-h-11"
        >
          Save template
          {isSaving ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : null}
        </Button>
      </CardContent>
    </Card>
  );
}
