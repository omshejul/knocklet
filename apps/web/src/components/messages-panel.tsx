"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";
import { Switch } from "@/components/ui/switch";
import {
  getTemplateFieldError,
  TemplateFieldEditor,
  type TemplateField,
} from "@/components/template-field-editor";
import { cn } from "@/lib/utils";
import { appear } from "@/lib/motion";

type MessageTemplate = {
  body: string;
  auto_send_enabled: boolean;
  delay_minutes: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export function MessagesPanel() {
  const reducedMotion = useReducedMotion();
  const [body, setBody] = useState("");
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [autoSend, setAutoSend] = useState(false);
  const [delayMinutes, setDelayMinutes] = useState(5);
  const [savedTemplate, setSavedTemplate] = useState<MessageTemplate | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.all([
      fetch(apiUrl + "/message-template", { cache: "no-store" }),
      fetch(apiUrl + "/message-template/fields", { cache: "no-store" }),
    ])
      .then(async ([templateResponse, fieldsResponse]) => {
        if (!fieldsResponse.ok) {
          throw new Error("Message fields could not be loaded.");
        }
        const template =
          templateResponse.status === 204
            ? null
            : ((await templateResponse.json()) as MessageTemplate);
        if (templateResponse.status !== 204 && !templateResponse.ok) {
          throw new Error("Template could not be loaded.");
        }
        return {
          template,
          fields: (await fieldsResponse.json()) as TemplateField[],
        };
      })
      .then((result) => {
        if (!active) return;
        setFields(result.fields);
        if (result.template) {
          setBody(result.template.body);
          setAutoSend(result.template.auto_send_enabled);
          setDelayMinutes(result.template.delay_minutes);
          setSavedTemplate(result.template);
        }
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
    const fieldError = getTemplateFieldError(body, fields);
    if (fieldError) {
      setError(fieldError);
      return;
    }
    if (delayMinutes < 0 || delayMinutes > 10_080) {
      setError("Delay must be between 0 and 10,080 minutes.");
      return;
    }
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
          delay_minutes: delayMinutes,
        }),
      });
      const data = (await response.json()) as MessageTemplate & { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? "Template could not be saved.");
      }
      setBody(data.body);
      setAutoSend(data.auto_send_enabled);
      setDelayMinutes(data.delay_minutes);
      setSavedTemplate(data);
      setConfirmation("Template saved.");
    } catch (saveError) {
      setError(
        saveError instanceof Error ? saveError.message : "Template could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const fieldError = getTemplateFieldError(body, fields);
  const isDirty = savedTemplate
    ? body !== savedTemplate.body ||
      autoSend !== savedTemplate.auto_send_enabled ||
      delayMinutes !== savedTemplate.delay_minutes
    : body.trim().length > 0 || autoSend || delayMinutes !== 5;

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-normal tracking-tight">Messages</h1>
        <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
          <span className="text-right">
            <span className="block">Send automatically after acceptance</span>
            <span className="block text-xs text-muted-foreground">
              Applies to uploads approved after saving
            </span>
          </span>
          <Switch
            checked={autoSend}
            onCheckedChange={setAutoSend}
            disabled={isLoading || isSaving}
          />
        </label>
      </div>

      <Card className="mt-5 shadow-xl shadow-black/40">
        <CardContent className="space-y-4 px-4 sm:px-5">
          {isLoading ? (
            <LoadingState>Loading message settings...</LoadingState>
          ) : null}

          <div>
            <label htmlFor="message-template" className="text-sm font-bold">
              Follow-up template
            </label>
            <TemplateFieldEditor
              id="message-template"
              value={body}
              onChange={setBody}
              fields={fields}
              disabled={isLoading || isSaving}
            />
            <p
              className={cn(
                "mt-1.5 text-xs text-muted-foreground",
                fieldError && "text-destructive",
              )}
            >
              {fieldError ||
                "Type { to insert a field."}
            </p>
          </div>

          <div>
            <label className="block text-sm font-bold">
              Send after acceptance
              <span className="mt-2 flex max-w-md items-center gap-2">
                <input
                  type="number"
                  min={0}
                  max={10_080}
                  value={delayMinutes}
                  onChange={(event) =>
                    setDelayMinutes(Number(event.target.value))
                  }
                  disabled={isLoading || isSaving}
                  className="h-11 min-w-0 flex-1 rounded-xl border border-input bg-transparent px-3 text-base font-normal tabular-nums outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
                <span className="text-sm font-normal text-muted-foreground">
                  minutes
                </span>
              </span>
            </label>
          </div>

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

          <AnimatePresence>
            {!isLoading && isDirty ? (
              <motion.div key="save-template" {...appear(reducedMotion)}>
                <Button
                  type="button"
                  onClick={saveTemplate}
                  disabled={
                    body.trim().length === 0 ||
                    Boolean(fieldError)
                  }
                  loading={isSaving}
                  className="min-h-11"
                >
                  Save template
                </Button>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </CardContent>
      </Card>
    </>
  );
}
