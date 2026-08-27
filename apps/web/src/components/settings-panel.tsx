"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@/components/ui/progress";
import { appear } from "@/lib/motion";

type RateLimitSettings = {
  date: string;
  daily_calls: number;
  daily_limit: number;
  default_daily_limit: number;
  remaining: number;
  calls_per_minute: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

async function responseError(response: Response, fallback: string) {
  const data = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  return data?.detail ?? fallback;
}

export function SettingsPanel() {
  const reducedMotion = useReducedMotion();
  const [settings, setSettings] = useState<RateLimitSettings | null>(null);
  const [dailyLimit, setDailyLimit] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(apiUrl + "/settings/rate-limits", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            await responseError(response, "Request usage could not be loaded."),
          );
        }
        return response.json() as Promise<RateLimitSettings>;
      })
      .then((data) => {
        if (!active) return;
        setSettings(data);
        setDailyLimit(String(data.daily_limit));
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

  async function saveLimit(event: FormEvent) {
    event.preventDefault();
    const parsedLimit = Number(dailyLimit);
    if (!Number.isInteger(parsedLimit) || parsedLimit < 1 || parsedLimit > 1000) {
      setError("Daily call limit must be between 1 and 1000.");
      return;
    }

    setIsSaving(true);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/settings/rate-limits", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ daily_limit: parsedLimit }),
      });
      if (!response.ok) {
        throw new Error(
          await responseError(response, "Daily call limit could not be saved."),
        );
      }
      const data = (await response.json()) as RateLimitSettings;
      setSettings(data);
      setDailyLimit(String(data.daily_limit));
      setConfirmation("Daily call limit saved. It applies to the next request.");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Daily call limit could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <LoadingState className="mt-5">Loading request usage...</LoadingState>;
  }

  if (!settings) {
    return (
      <Alert variant="destructive" className="mt-5">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const usagePercent = Math.min(
    100,
    Math.round((settings.daily_calls / settings.daily_limit) * 100),
  );
  const parsedLimit = Number(dailyLimit);
  const isDirty = parsedLimit !== settings.daily_limit;
  const showRiskWarning =
    parsedLimit > settings.default_daily_limit ||
    parsedLimit > settings.daily_limit;

  return (
    <Card className="mt-5 shadow-xl shadow-black/40">
      <CardHeader className="border-b">
        <CardTitle>LinkedIn request budget</CardTitle>
        <CardDescription>
          Knocklet counts LinkedIn reads, page loads, and sends against one daily
          budget.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 px-4 sm:px-5">
        <Progress value={usagePercent}>
          <ProgressLabel>Today&apos;s usage</ProgressLabel>
          <ProgressValue>
            {() =>
              `${settings.daily_calls} of ${settings.daily_limit} calls`
            }
          </ProgressValue>
        </Progress>
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <p>
            <span className="block text-2xl tabular-nums">
              {settings.remaining}
            </span>
            <span className="text-muted-foreground">calls remaining today</span>
          </p>
          <p>
            <span className="block text-2xl tabular-nums">
              {settings.calls_per_minute}
            </span>
            <span className="text-muted-foreground">calls per rolling minute</span>
          </p>
        </div>

        <form onSubmit={saveLimit} className="space-y-4 border-t pt-5">
          <label htmlFor="daily-call-limit" className="block text-sm font-bold">
            Daily call limit
          </label>
          <div className="flex max-w-sm items-center gap-2">
            <input
              id="daily-call-limit"
              type="number"
              min={1}
              max={1000}
              value={dailyLimit}
              onChange={(event) => {
                setDailyLimit(event.target.value);
                setConfirmation("");
                setError("");
              }}
              disabled={isSaving}
              aria-invalid={Boolean(error)}
              className="h-11 min-w-0 flex-1 rounded-xl border border-input bg-transparent px-3 text-base tabular-nums outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive"
            />
            <span className="text-sm text-muted-foreground">calls / day</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Default: {settings.default_daily_limit}. If needed, try 120 before
            raising it again.
          </p>

          <AnimatePresence initial={false}>
            {showRiskWarning ? (
              <motion.div key="limit-warning" {...appear(reducedMotion)}>
                <Alert className="border-warning/50 text-warning">
                  <AlertTriangle aria-hidden="true" />
                  <AlertTitle>Higher limits increase account risk</AlertTitle>
                  <AlertDescription className="text-warning/90">
                    LinkedIn may restrict accounts for automated activity. No
                    daily limit is guaranteed safe, so keep this as low as your
                    workload permits.
                  </AlertDescription>
                </Alert>
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

          <Button
            type="submit"
            loading={isSaving}
            disabled={!isDirty}
            className="min-h-11"
          >
            Save limit
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
