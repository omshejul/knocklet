"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";
import { Switch } from "@/components/ui/switch";
import { appear } from "@/lib/motion";

type AcceptanceCheckSettingsValue = {
  auto_check: boolean;
  frequency_minutes: number;
  default_frequency_minutes: number;
  minimum_frequency_minutes: number;
  maximum_frequency_minutes: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

async function responseError(response: Response, fallback: string) {
  const data = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  return data?.detail ?? fallback;
}

export function AcceptanceCheckSettings() {
  const reducedMotion = useReducedMotion();
  const [settings, setSettings] =
    useState<AcceptanceCheckSettingsValue | null>(null);
  const [autoCheck, setAutoCheck] = useState(true);
  const [frequency, setFrequency] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(apiUrl + "/settings/acceptance-checks", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            await responseError(response, "Acceptance settings could not be loaded."),
          );
        }
        return response.json() as Promise<AcceptanceCheckSettingsValue>;
      })
      .then((data) => {
        if (!active) return;
        setSettings(data);
        setAutoCheck(data.auto_check);
        setFrequency(String(data.frequency_minutes));
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

  async function saveChecks(event: FormEvent) {
    event.preventDefault();
    if (!settings) {
      setError("Acceptance settings are not loaded.");
      return;
    }

    const parsedFrequency = Number(frequency);
    const frequencyIsValid =
      Number.isInteger(parsedFrequency) &&
      parsedFrequency >= settings.minimum_frequency_minutes &&
      parsedFrequency <= settings.maximum_frequency_minutes;
    if (autoCheck && !frequencyIsValid) {
      setError(
        `Frequency must be between ${settings.minimum_frequency_minutes} and ` +
          `${settings.maximum_frequency_minutes} minutes.`,
      );
      return;
    }

    setIsSaving(true);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/settings/acceptance-checks", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auto_check: autoCheck,
          frequency_minutes: frequencyIsValid
            ? parsedFrequency
            : settings.frequency_minutes,
        }),
      });
      if (!response.ok) {
        throw new Error(
          await responseError(response, "Acceptance settings could not be saved."),
        );
      }
      const data = (await response.json()) as AcceptanceCheckSettingsValue;
      setSettings(data);
      setAutoCheck(data.auto_check);
      setFrequency(String(data.frequency_minutes));
      setConfirmation(
        data.auto_check
          ? `Automatic checks will run every ${data.frequency_minutes} minutes.`
          : "Automatic checks are off. Check now remains available.",
      );
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Acceptance settings could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <LoadingState>Loading acceptance settings...</LoadingState>;
  }

  if (!settings) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const parsedFrequency = Number(frequency);
  const frequencyIsValid =
    Number.isInteger(parsedFrequency) &&
    parsedFrequency >= settings.minimum_frequency_minutes &&
    parsedFrequency <= settings.maximum_frequency_minutes;
  const isDirty =
    autoCheck !== settings.auto_check ||
    (autoCheck && parsedFrequency !== settings.frequency_minutes);
  const checksPerDay = frequencyIsValid
    ? Math.ceil(1440 / parsedFrequency)
    : 0;

  return (
    <Card className="shadow-xl shadow-black/40">
      <CardHeader className="border-b">
        <CardTitle>Acceptance checks</CardTitle>
        <CardDescription>
          Check pending invitations to find new connections.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4 sm:px-5">
        <form onSubmit={saveChecks} className="space-y-4">
          <label className="flex min-h-11 cursor-pointer items-center justify-between gap-4">
            <span>
              <span className="block text-sm font-bold">Check automatically</span>
              <span className="block text-xs text-muted-foreground">
                Runs only while invitations are pending
              </span>
            </span>
            <Switch
              checked={autoCheck}
              onCheckedChange={(checked) => {
                setAutoCheck(checked);
                setConfirmation("");
                setError("");
              }}
              disabled={isSaving}
              aria-label="Check acceptances automatically"
            />
          </label>

          <AnimatePresence initial={false}>
            {autoCheck ? (
              <motion.div
                key="acceptance-frequency"
                {...appear(reducedMotion)}
                className="space-y-2 border-t pt-4"
              >
                <label
                  htmlFor="acceptance-check-frequency"
                  className="block text-sm font-bold"
                >
                  Check every
                </label>
                <div className="flex max-w-sm items-center gap-2">
                  <input
                    id="acceptance-check-frequency"
                    type="number"
                    min={settings.minimum_frequency_minutes}
                    max={settings.maximum_frequency_minutes}
                    value={frequency}
                    onChange={(event) => {
                      setFrequency(event.target.value);
                      setConfirmation("");
                      setError("");
                    }}
                    disabled={isSaving}
                    aria-invalid={Boolean(error)}
                    className="h-11 min-w-0 flex-1 rounded-xl border border-input bg-transparent px-3 text-base tabular-nums outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive"
                  />
                  <span className="text-sm text-muted-foreground">minutes</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {frequencyIsValid
                    ? `Up to ${checksPerDay} checks per day while invitations are pending. Each check uses at least one call.`
                    : `Enter ${settings.minimum_frequency_minutes} to ${settings.maximum_frequency_minutes} minutes.`}
                </p>
              </motion.div>
            ) : null}
          </AnimatePresence>

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

          <AnimatePresence initial={false}>
            {isDirty ? (
              <motion.div key="save-acceptance-checks" {...appear(reducedMotion)}>
                <Button type="submit" loading={isSaving} className="min-h-11">
                  Save acceptance checks
                </Button>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </form>
      </CardContent>
    </Card>
  );
}
